import asyncio
import re
from pathlib import Path
from typing import Any, Callable

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from app.answer_engine import AnswerEngine
from app.schema import load_schema
from app.submissions import SUBMISSIONS_DIR, create_batch, finish_batch, save_submission

LogFn = Callable[[str, str], Any]

# JavaScript helpers run inside the Enketo page for reliable interaction.
_FILL_QUESTION_JS = """
({ questionNum, qType, value, rankItem }) => {
  const normalize = (s) => String(s || '').replace(/\\s+/g, ' ').trim().toLowerCase();

  const findQuestion = () => {
    const questions = Array.from(document.querySelectorAll('.question'));
    if (rankItem) {
      return questions.find((el) => {
        const t = el.innerText || '';
        return t.includes('Rank for: ' + rankItem);
      });
    }
    const re = new RegExp('(^|\\\\n)\\\\s*' + questionNum + '\\\\.(\\\\s|$)');
    return questions.find((el) => re.test(el.innerText || ''));
  };

  const q = findQuestion();
  if (!q) return { ok: false, reason: 'not_found' };
  q.scrollIntoView({ block: 'center', behavior: 'instant' });

  const fire = (el) => {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
  };

  const fillTextLike = (raw) => {
    const field = q.querySelector('textarea')
      || q.querySelector('input[type="text"]')
      || q.querySelector('input[type="search"]')
      || q.querySelector('input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"])');
    if (!field) return false;
    const value = Array.isArray(raw) ? raw.join(', ') : raw;
    field.focus();
    field.click();
    field.value = String(value ?? '');
    fire(field);
    return true;
  };

  const setSelectValue = (raw, multiple = false) => {
    const sel = q.querySelector('select');
    if (!sel) return false;
    const wanted = (Array.isArray(raw) ? raw : [raw]).map(normalize);
    if (!wanted.length) return false;
    const options = Array.from(sel.options || []);
    const findOption = (want) =>
      options.find((o) => normalize(o.textContent) === want)
      || options.find((o) => normalize(o.label) === want)
      || options.find((o) => normalize(o.textContent).includes(want));

    if (multiple || sel.multiple) {
      let matched = 0;
      options.forEach((o) => { o.selected = false; });
      for (const want of wanted) {
        const opt = findOption(want);
        if (opt) {
          opt.selected = true;
          matched += 1;
        }
      }
      if (matched === 0) return false;
      fire(sel);
      return matched === wanted.length;
    }

    const opt = findOption(wanted[0]);
    if (!opt) return false;
    sel.value = opt.value;
    opt.selected = true;
    fire(sel);
    return true;
  };

  const findChoice = (choice) => {
    const want = normalize(choice);
    const labels = Array.from(q.querySelectorAll('label'));
    let lbl = labels.find((l) => normalize(l.innerText) === want);
    if (!lbl) lbl = labels.find((l) => normalize(l.innerText).startsWith(want));
    if (!lbl) lbl = labels.find((l) => normalize(l.innerText).includes(want));
    if (lbl) {
      const forId = lbl.getAttribute('for');
      const input = forId ? document.getElementById(forId) : lbl.querySelector('input');
      return { lbl, input };
    }
    const inputs = Array.from(q.querySelectorAll('input[type="checkbox"], input[type="radio"]'));
    for (const inp of inputs) {
      const l = inp.id && document.querySelector('label[for="' + inp.id + '"]');
      if (l && normalize(l.innerText).includes(want)) return { lbl: l, input: inp };
    }
    return null;
  };

  const ensureChoice = (choice) => {
    const found = findChoice(choice);
    if (!found) return false;
    const { lbl, input } = found;
    if (input && input.checked) return true;
    if (lbl) lbl.click();
    else if (input) input.click();
    if (input && !input.checked) {
      if (lbl) lbl.click();
      else input.click();
    }
    return input ? input.checked : true;
  };

  if (qType === 'text') {
    return fillTextLike(value) ? { ok: true } : { ok: false, reason: 'no_input' };
  }

  if (qType === 'integer' || qType === 'decimal') {
    const field = q.querySelector('input[type="number"]') || q.querySelector('input');
    if (!field) return { ok: false, reason: 'no_input' };
    field.focus();
    field.click();
    field.value = String(value);
    fire(field);
    return { ok: true };
  }

  if (qType === 'select_one') {
    if (ensureChoice(value)) return { ok: true };
    if (setSelectValue(value, false)) return { ok: true };
    if (fillTextLike(value)) return { ok: true };
    return { ok: false, reason: 'no_choice' };
  }

  if (qType === 'select_multiple') {
    const choices = Array.isArray(value) ? value : [value];
    if (!choices.length) return { ok: false, reason: 'no_choice', count: 0 };
    let matched = 0;
    for (const c of choices) if (ensureChoice(c)) matched++;
    if (matched === choices.length) return { ok: true, count: matched };
    if (setSelectValue(choices, true)) return { ok: true, count: choices.length };
    if (fillTextLike(choices)) return { ok: true, count: choices.length };
    return { ok: false, reason: 'no_choice', count: matched };
  }

  return { ok: false, reason: 'unknown_type' };
}
"""

_GOTO_SECTION_JS = """
(sectionPrefix) => {
  const buttons = Array.from(document.querySelectorAll('button, .or-group-label, .or-appearance-compact'));
  const btn = buttons.find((b) => (b.innerText || '').toUpperCase().includes(sectionPrefix.toUpperCase()));
  if (btn) { btn.click(); return true; }
  return false;
}
"""

_CLICK_NEXT_JS = """
() => {
  const links = Array.from(document.querySelectorAll('a, button'));
  const next = links.find((a) => /^next$/i.test((a.innerText || '').trim()));
  if (next) { next.click(); return true; }
  return false;
}
"""

_HANDLE_DRAFT_PROMPT_JS = """
({ mode }) => {
  const norm = (s) => String(s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  const isVisible = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const controls = Array.from(document.querySelectorAll('button, a, [role="button"], .btn'))
    .filter(isVisible);
  const choose = (terms) => controls.find((el) => {
    const t = norm(el.innerText || el.textContent);
    return terms.some((x) => t.includes(x));
  });

  // Enketo draft prompt wording varies by version/theme.
  const loadTerms = ['load', 'restore', 'continue'];
  const discardTerms = ['discard', 'delete', 'start over', 'new form', 'clear'];

  const target = mode === 'load' ? (choose(loadTerms) || choose(discardTerms)) : (choose(discardTerms) || choose(loadTerms));
  if (!target) return { handled: false };
  target.click();
  return { handled: true, action: mode };
}
"""

_GOTO_QUESTION_JS = """
(questionNum) => {
  // Try to find and click page navigation link
  const links = Array.from(document.querySelectorAll('a.page-link, .page-link, .or-navigate a'));
  const link = links.find((a) => {
    const t = (a.innerText || '').trim();
    return t.startsWith(String(questionNum) + '.');
  });
  if (link) { 
    link.click(); 
    return true; 
  }
  
  // Fallback: try to scroll to the question directly
  const questions = Array.from(document.querySelectorAll('.question'));
  const re = new RegExp('(^|\\n)\\s*' + questionNum + '\\.\\s');
  const q = questions.find((el) => re.test(el.innerText || ''));
  if (q) {
    q.scrollIntoView({ block: 'center', behavior: 'instant' });
    // Ensure question is visible
    let p = q;
    while (p) {
      if (p.style) {
        p.style.removeProperty('display');
        p.style.removeProperty('height');
        p.style.removeProperty('max-height');
        p.style.removeProperty('overflow');
      }
      if (p.classList) {
        p.classList.remove('or-appearance-minimal', 'or-previous', 'or-hidden', 'disabled', 'hidden');
      }
      p = p.parentElement;
    }
    return true;
  }
  
  return false;
}
"""

_LIST_UNANSWERED_REQUIRED_JS = """
() => {
  const norm = (s) => String(s || '').replace(/\\s+/g, ' ').trim();
  const parseNum = (q) => {
    const label = q.querySelector('.question-label');
    const text = norm(label ? label.innerText : q.innerText);
    const m = text.match(/^(\\d+)\\./);
    return m ? Number(m[1]) : null;
  };
  const inferType = (q) => {
    if (q.querySelector('input[type="radio"]')) return 'select_one';
    if (q.querySelector('input[type="checkbox"]')) return 'select_multiple';
    const sel = q.querySelector('select');
    if (sel) return sel.multiple ? 'select_multiple' : 'select_one';
    if (q.querySelector('input[type="number"]')) return 'integer';
    return 'text';
  };
  const isAnswered = (q) => {
    const radios = q.querySelectorAll('input[type="radio"]');
    if (radios.length) return Array.from(radios).some((x) => x.checked);
    const checks = q.querySelectorAll('input[type="checkbox"]');
    if (checks.length) return Array.from(checks).some((x) => x.checked);
    const sel = q.querySelector('select');
    if (sel) {
      if (sel.multiple) return Array.from(sel.selectedOptions || []).length > 0;
      return norm(sel.value).length > 0;
    }
    const field = q.querySelector(
      'textarea, input[type="text"], input[type="number"], input[type="search"], input:not([type])'
    );
    if (!field) return false;
    return norm(field.value).length > 0;
  };
  const isRequired = (q) => {
    if (q.querySelector('.required')) return true;
    const field = q.querySelector('input, textarea, select');
    if (!field) return false;
    const req = field.getAttribute('data-required');
    return req && req.toLowerCase().includes('true');
  };
  const isVisible = (q) => {
    if (q.classList.contains('disabled') || q.classList.contains('or-branch') && q.classList.contains('disabled')) {
      return false;
    }
    const r = q.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const choices = (q) => {
    const labels = Array.from(q.querySelectorAll('label'))
      .map((l) => norm(l.innerText))
      .filter(Boolean);
    if (labels.length) return labels;
    const sel = q.querySelector('select');
    if (!sel) return [];
    return Array.from(sel.options || [])
      .map((o) => norm(o.textContent))
      .filter(Boolean);
  };

  const out = [];
  const seen = new Set();
  for (const q of Array.from(document.querySelectorAll('.question'))) {
    if (!isVisible(q) || !isRequired(q)) continue;
    if (isAnswered(q)) continue;
    const num = parseNum(q);
    if (num == null || seen.has(num)) continue;
    seen.add(num);
    out.push({
      number: num,
      type: inferType(q),
      choices: choices(q).slice(0, 20),
    });
  }
  out.sort((a, b) => a.number - b.number);
  return out;
}
"""


class SurveyFiller:
    SURVEY_URL = "https://ee.kobotoolbox.org/x/lJHKBgCj"
    FIELD_TIMEOUT_MS = 10000

    def __init__(self, log: LogFn | None = None):
        self.log = log or (lambda msg, level="info": None)
        self._stop_requested = False
        self.schema = load_schema()
        self.engine = AnswerEngine()
        self._batch_id: str | None = None

    def stop(self) -> None:
        self._stop_requested = True

    def preview_responses(self, count: int) -> list[dict[str, Any]]:
        return [self.engine.generate(i) for i in range(count)]

    def _should_answer(self, question: dict[str, Any], answers: dict[str, Any]) -> bool:
        cond = question.get("conditional")
        if not cond:
            return True
        parent_val = answers.get(cond["question"])
        if isinstance(parent_val, list):
            return cond["value"] in parent_val
        return parent_val == cond["value"]

    def _build_responses(self, respondent_index: int) -> dict[str, Any]:
        return self.engine.generate(respondent_index)

    def _all_questions(self) -> list[dict[str, Any]]:
        questions = []
        for section in self.schema["sections"]:
            questions.extend(section["questions"])
        return questions

    async def _wait_for_form(self, page: Page, *, submit: bool) -> None:
        page.set_default_timeout(60000)
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                await page.goto(self.SURVEY_URL, wait_until="domcontentloaded", timeout=90000)
                # Handle draft restore prompt:
                # - test runs: discard previous draft
                # - submit runs: load previous draft and continue to completion
                draft_mode = "load" if submit else "discard"
                for _ in range(3):
                    handled = await page.evaluate(_HANDLE_DRAFT_PROMPT_JS, {"mode": draft_mode})
                    if not handled or not handled.get("handled"):
                        break
                    await asyncio.sleep(0.8)
                await page.wait_for_selector("form.or", timeout=60000)
                await page.wait_for_selector(".question", timeout=60000)
                break
            except PlaywrightTimeoutError:
                if attempt >= attempts:
                    raise
                backoff_s = 3 * attempt
                self.log(
                    f"Survey load timed out (attempt {attempt}/{attempts}); retrying in {backoff_s}s…",
                    "warn",
                )
                try:
                    await page.goto("about:blank", wait_until="domcontentloaded", timeout=15000)
                except Exception:
                    pass
                await asyncio.sleep(backoff_s)
        page.set_default_timeout(self.FIELD_TIMEOUT_MS)
        await asyncio.sleep(2.0)

    async def _open_section(self, page: Page, section: dict[str, Any]) -> None:
        """Open an Enketo section so its questions become visible."""
        sid = section["id"]
        prefixes = {
            "A": "SECTION A",
            "B": "SECTION B",
            "RANK": "CHALLENGE SEVERITY",
            "C": "SECTION C",
            "D": "SECTION D",
        }
        prefix = prefixes.get(sid, section["title"][:20])
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(prefix[:12]), re.I))
            if await btn.count() > 0:
                await btn.first.click(timeout=5000)
            else:
                await page.evaluate(_GOTO_SECTION_JS, prefix)
            await asyncio.sleep(0.8)
        except Exception:
            pass

    async def _click_next(self, page: Page) -> None:
        try:
            await page.evaluate(_CLICK_NEXT_JS)
            await asyncio.sleep(0.5)
        except Exception:
            pass

    async def _goto_question(self, page: Page, number: int) -> None:
        try:
            await page.evaluate(_GOTO_QUESTION_JS, number)
            await asyncio.sleep(0.35)
        except Exception:
            pass

    async def _fill_via_js(
        self,
        page: Page,
        question: dict[str, Any],
        value: Any,
        *,
        rank_item: str | None = None,
    ) -> bool:
        qtype = question["type"]
        if qtype == "rank":
            return False

        payload = {
            "questionNum": str(question["number"]),
            "qType": qtype,
            "value": value,
            "rankItem": rank_item,
        }
        try:
            result = await page.evaluate(_FILL_QUESTION_JS, payload)
            return bool(result and result.get("ok"))
        except Exception:
            return False

    async def _fill_rank_item(self, page: Page, item: str, rank: int) -> bool:
        payload = {
            "questionNum": "48",
            "qType": "integer",
            "value": str(rank),
            "rankItem": item,
        }
        try:
            result = await page.evaluate(_FILL_QUESTION_JS, payload)
            return bool(result and result.get("ok"))
        except Exception:
            return False

    async def _fill_question(
        self,
        page: Page,
        question: dict[str, Any],
        value: Any,
    ) -> bool:
        number = question["number"]
        self.log(f"Filling Q{number} ({question['type']})...", "info")
        await self._goto_question(page, number)

        if question["type"] == "rank":
            ok = True
            for item, rank in value.items():
                await self._goto_question(page, number)
                item_ok = await self._fill_rank_item(page, item, rank)
                if not item_ok:
                    self.log(f"Q{number} rank '{item}': not filled (hidden or not found)", "warn")
                    ok = False
                await asyncio.sleep(0.2)
            return ok

        # Aggressive retry logic - more retries with longer delays
        max_retries = 5
        delays = [0.2, 0.5, 1.0, 1.5, 2.0]
        
        for attempt in range(max_retries):
            if await self._fill_via_js(page, question, value):
                return True
            
            if attempt < max_retries - 1:
                self.log(f"Q{number}: retry {attempt + 1}/{max_retries - 1}", "warn")
                await asyncio.sleep(delays[attempt])
                await self._goto_question(page, number)

        self.log(f"Q{number}: failed after {max_retries} attempts", "warn")
        return False

    async def _list_unanswered_required(self, page: Page) -> list[dict[str, Any]]:
        try:
            result = await page.evaluate(_LIST_UNANSWERED_REQUIRED_JS)
            if isinstance(result, list):
                return result
            return []
        except Exception:
            return []

    def _fallback_value_for_live_question(
        self,
        question: dict[str, Any],
        answers: dict[str, Any],
    ) -> Any:
        qnum = question.get("number")
        value = answers.get(f"q{qnum}") if qnum is not None else None
        if value is not None:
            return value
        qtype = question.get("type")
        options = [c for c in (question.get("choices") or []) if c and c != "Other (Specify)"]
        if qtype == "select_multiple":
            return options[:2] if options else ["Yes"]
        if qtype == "select_one":
            return options[0] if options else "Yes"
        if qtype in ("integer", "decimal"):
            return 1
        return "N/A"

    async def _take_screenshot(self, page: Page, batch_id: str, respondent: int) -> str:
        batch_path = SUBMISSIONS_DIR / batch_id
        batch_path.mkdir(parents=True, exist_ok=True)
        filename = f"respondent_{respondent:03d}.png"
        filepath = batch_path / filename
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.3)
        await page.screenshot(path=str(filepath), full_page=True)
        return filename

    async def _submit_form(self, page: Page) -> bool:
        for _ in range(10):
            submit_btn = page.locator(
                "button#submit-form, .submit button, button.submit, button:has-text('Submit')"
            )
            if await submit_btn.count() == 0:
                submit_btn = page.get_by_role("button", name=re.compile("submit", re.IGNORECASE))
            if await submit_btn.count() > 0:
                await submit_btn.first.scroll_into_view_if_needed()
                await submit_btn.first.click(timeout=8000)
                await asyncio.sleep(2)
                return True
            if not await page.evaluate(_CLICK_NEXT_JS):
                break
            await asyncio.sleep(0.5)
        return False

    async def fill_one(
        self,
        page: Page,
        respondent_index: int,
        *,
        submit: bool = True,
        delay_ms: int = 500,
        batch_id: str | None = None,
        answers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        answers = answers or self._build_responses(respondent_index)
        respondent_num = respondent_index + 1
        name = answers.get("_meta", {}).get("name", f"Respondent {respondent_num}")
        self.log(f"#{respondent_num} {name}: loading survey…", "info")

        await self._wait_for_form(page, submit=submit)

        filled = 0
        skipped = 0

        for section in self.schema["sections"]:
            if self._stop_requested:
                break

            await self._open_section(page, section)
            self.log(f"#{respondent_num}: filling section {section['id']}…", "info")

            for question in section["questions"]:
                if self._stop_requested:
                    break
                if not self._should_answer(question, answers):
                    self.log(f"Q{question['number']}: skipped (conditional not met)", "info")
                    continue
                value = answers.get(question["id"])
                if value is None:
                    skipped += 1
                    self.log(f"Q{question['number']}: skipped (no value generated)", "warn")
                    continue

                try:
                    ok = await self._fill_question(page, question, value)
                    if ok:
                        filled += 1
                    else:
                        skipped += 1
                        self.log(f"Q{question['number']}: skipped (not visible on form)", "warn")
                except Exception as e:
                    skipped += 1
                    if "closed" in str(e).lower():
                        raise
                    short = str(e).split("\n")[0][:120]
                    self.log(f"Q{question['number']}: skipped — {short}", "warn")

                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000)
                else:
                    # Small delay even if delay_ms is 0 to allow form to stabilize
                    await asyncio.sleep(0.15)

            await self._click_next(page)

        # Safety pass: fill any visible required fields left unanswered on the live form.
        for _ in range(2):
            pending = await self._list_unanswered_required(page)
            if not pending:
                break
            self.log(f"#{respondent_num}: backfilling {len(pending)} required unanswered question(s)", "warn")
            progress = 0
            for live_q in pending:
                q_for_fill = {
                    "number": live_q["number"],
                    "type": live_q.get("type", "text"),
                }
                value = self._fallback_value_for_live_question(live_q, answers)
                try:
                    ok = await self._fill_question(page, q_for_fill, value)
                    if ok:
                        filled += 1
                        progress += 1
                    else:
                        skipped += 1
                except Exception as e:
                    skipped += 1
                    if "closed" in str(e).lower():
                        raise
            if progress == 0:
                break

        screenshot_file = None
        if batch_id:
            try:
                screenshot_file = await self._take_screenshot(page, batch_id, respondent_num)
                self.log(f"#{respondent_num}: screenshot saved", "info")
            except Exception as e:
                if "closed" not in str(e).lower():
                    self.log(f"#{respondent_num}: screenshot failed — {e}", "warn")

        if submit and not self._stop_requested:
            submitted = await self._submit_form(page)
            status = "submitted" if submitted else "filled (submit not found)"
        else:
            status = "filled (preview)" if not submit else "filled"

        self.log(
            f"#{respondent_num} {name}: {status} — {filled} filled, {skipped} skipped",
            "success" if filled > 50 else "warn",
        )

        result = {
            "respondent": respondent_num,
            "answers": answers,
            "status": status,
            "fields_filled": filled,
            "fields_skipped": skipped,
            "screenshot": screenshot_file,
            "batch_id": batch_id,
        }

        if batch_id:
            save_submission(
                batch_id,
                respondent_num,
                answers=answers,
                status=status,
                fields_filled=filled,
                screenshot_path=screenshot_file,
            )

        return result

    async def run_batch(
        self,
        count: int = 1,
        *,
        headless: bool = True,
        submit: bool = True,
        delay_ms: int = 300,
        between_submissions_ms: int = 2000,
    ) -> list[dict[str, Any]]:
        self._stop_requested = False
        results: list[dict[str, Any]] = []
        batch_id = create_batch(count, submit=submit)
        self._batch_id = batch_id
        self.log(f"Batch {batch_id} started ({count} submission(s), submit={submit})", "info")

        if not headless:
            self.log("Keep the browser window open until each respondent finishes.", "info")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )

                for i in range(count):
                    if self._stop_requested:
                        self.log("Stopped by user", "warn")
                        break

                    answers = self._build_responses(i)
                    page = await context.new_page()
                    try:
                        result = await self.fill_one(
                            page,
                            i,
                            submit=submit,
                            delay_ms=delay_ms,
                            batch_id=batch_id,
                            answers=answers,
                        )
                        results.append(result)
                        if submit and result.get("status") != "submitted":
                            self.log(
                                f"Respondent {i + 1} was not submitted; stopping batch before next respondent.",
                                "error",
                            )
                            break
                    except Exception as e:
                        msg = str(e)
                        if "closed" in msg.lower():
                            self.log(
                                f"Respondent {i + 1} failed: browser was closed. "
                                "Do not close the browser window during Quick Test.",
                                "error",
                            )
                        else:
                            self.log(f"Respondent {i + 1} failed: {e}", "error")
                        err_result = {
                            "respondent": i + 1,
                            "status": "error",
                            "error": msg,
                            "batch_id": batch_id,
                        }
                        results.append(err_result)
                        if batch_id:
                            save_submission(
                                batch_id,
                                i + 1,
                                answers=answers,
                                status="error",
                                fields_filled=0,
                                error=msg,
                            )
                    finally:
                        try:
                            await page.close()
                        except Exception:
                            pass

                    if i < count - 1 and between_submissions_ms > 0:
                        await asyncio.sleep(between_submissions_ms / 1000)

                await browser.close()
        finally:
            finish_batch(batch_id, results)
        self.log(f"Batch {batch_id} complete — review in Submissions tab", "success")
        return results
