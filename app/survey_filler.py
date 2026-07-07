import asyncio
import re
from pathlib import Path
from typing import Any, Callable

from playwright.async_api import Page, async_playwright

from app.answer_engine import AnswerEngine
from app.schema import load_schema
from app.submissions import SUBMISSIONS_DIR, create_batch, finish_batch, save_submission

LogFn = Callable[[str, str], Any]

# JavaScript helpers run inside the Enketo page for reliable interaction.
_FILL_QUESTION_JS = """
({ questionNum, qType, value, rankItem }) => {
  const expandParents = (el) => {
    let p = el;
    while (p) {
      if (p.style) {
        p.style.removeProperty('display');
        p.style.removeProperty('height');
        p.style.removeProperty('max-height');
        p.style.removeProperty('overflow');
      }
      if (p.classList) {
        p.classList.remove('or-appearance-minimal', 'or-previous', 'or-hidden', 'disabled');
      }
      p = p.parentElement;
    }
  };

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
  expandParents(q);
  q.scrollIntoView({ block: 'center', behavior: 'instant' });

  const fire = (el) => {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
  };

  const clickLabel = (choice) => {
    const want = String(choice).trim().toLowerCase();
    const labels = Array.from(q.querySelectorAll('label'));
    let lbl = labels.find((l) => l.innerText.trim().toLowerCase() === want);
    if (!lbl) lbl = labels.find((l) => l.innerText.trim().toLowerCase().startsWith(want));
    if (lbl) { lbl.click(); return true; }
    const inputs = Array.from(q.querySelectorAll('input[type="checkbox"], input[type="radio"]'));
    for (const inp of inputs) {
      const l = inp.id && document.querySelector('label[for="' + inp.id + '"]');
      if (l && l.innerText.trim().toLowerCase().includes(want)) { l.click(); return true; }
    }
    return false;
  };

  if (qType === 'text') {
    const field = q.querySelector('textarea') || q.querySelector('input[type="text"]')
      || q.querySelector('input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"])');
    if (!field) return { ok: false, reason: 'no_input' };
    field.focus();
    field.click();
    field.value = String(value);
    fire(field);
    return { ok: true };
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
    return clickLabel(value) ? { ok: true } : { ok: false, reason: 'no_choice' };
  }

  if (qType === 'select_multiple') {
    const choices = Array.isArray(value) ? value : [value];
    let n = 0;
    for (const c of choices) if (clickLabel(c)) n++;
    return n > 0 ? { ok: true, count: n } : { ok: false, reason: 'no_choice' };
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
        # Only allow skipping q2 (phone number) - all other questions must be answered
        if question["id"] == "q2":
            cond = question.get("conditional")
            if not cond:
                return True
            parent_val = answers.get(cond["question"])
            if isinstance(parent_val, list):
                return cond["value"] in parent_val
            return parent_val == cond["value"]
        
        # For all other questions, always return True to force filling
        return True

    def _build_responses(self, respondent_index: int) -> dict[str, Any]:
        return self.engine.generate(respondent_index)

    def _all_questions(self) -> list[dict[str, Any]]:
        questions = []
        for section in self.schema["sections"]:
            questions.extend(section["questions"])
        return questions

    async def _wait_for_form(self, page: Page) -> None:
        page.set_default_timeout(60000)
        await page.goto(self.SURVEY_URL, wait_until="domcontentloaded")
        await page.wait_for_selector("form.or", timeout=60000)
        await page.wait_for_selector(".question", timeout=60000)
        
        # Force form visibility by removing hidden/display properties
        await page.evaluate("""
            () => {
                const form = document.querySelector('form.or');
                if (form) {
                    form.style.removeProperty('display');
                    form.style.removeProperty('visibility');
                    form.classList.remove('or-hidden', 'hidden');
                }
                document.querySelectorAll('.or-group, fieldset, .or-appearance-fieldset, .question').forEach(el => {
                    el.style.removeProperty('display');
                    el.style.removeProperty('visibility');
                    el.classList.remove('or-hidden', 'hidden', 'or-appearance-minimal');
                });
            }
        """)
        
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
        
        # Force all sections to be visible regardless of navigation
        await page.evaluate("""
            () => {
                document.querySelectorAll('.or-group, fieldset, .or-appearance-fieldset, .question, .or-section').forEach(el => {
                    el.style.removeProperty('display');
                    el.style.removeProperty('height');
                    el.style.removeProperty('visibility');
                    el.style.removeProperty('max-height');
                    el.style.removeProperty('overflow');
                    el.classList.remove('or-appearance-minimal', 'or-hidden', 'hidden', 'or-previous', 'disabled');
                });
            }
        """)
        
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(prefix[:12]), re.I))
            if await btn.count() > 0:
                await btn.first.click(timeout=5000)
            else:
                await page.evaluate(_GOTO_SECTION_JS, prefix)
            await asyncio.sleep(1.0)
            await page.evaluate("""
                () => {
                    document.querySelectorAll('.or-group, fieldset, .or-appearance-fieldset, .question').forEach(el => {
                        el.style.removeProperty('display');
                        el.style.removeProperty('height');
                        el.style.removeProperty('visibility');
                        el.classList.remove('or-appearance-minimal', 'or-hidden', 'hidden');
                    });
                }
            """)
            await asyncio.sleep(0.5)
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
            # Force visibility before each attempt
            await page.evaluate("""
                () => {
                    document.querySelectorAll('.question, .or-group, fieldset').forEach(el => {
                        el.style.removeProperty('display');
                        el.style.removeProperty('visibility');
                        el.classList.remove('or-hidden', 'hidden', 'or-appearance-minimal');
                    });
                }
            """)
            await asyncio.sleep(0.1)
            
            if await self._fill_via_js(page, question, value):
                return True
            
            if attempt < max_retries - 1:
                self.log(f"Q{number}: retry {attempt + 1}/{max_retries - 1}", "warn")
                await asyncio.sleep(delays[attempt])
                await self._goto_question(page, number)

        self.log(f"Q{number}: failed after {max_retries} attempts", "warn")
        return False

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
        return False

    async def fill_one(
        self,
        page: Page,
        respondent_index: int,
        *,
        submit: bool = True,
        delay_ms: int = 500,
        batch_id: str | None = None,
    ) -> dict[str, Any]:
        answers = self._build_responses(respondent_index)
        respondent_num = respondent_index + 1
        name = answers.get("_meta", {}).get("name", f"Respondent {respondent_num}")
        self.log(f"#{respondent_num} {name}: loading survey…", "info")

        await self._wait_for_form(page)

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
                    # Don't skip - try to fill with empty/default value
                    self.log(f"Q{question['number']}: no value generated, attempting fill anyway", "warn")
                    value = "" if question["type"] in ["text", "integer", "decimal"] else "Yes"

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
        workers: int = 1,
    ) -> list[dict[str, Any]]:
        self._stop_requested = False
        ordered_results: list[dict[str, Any] | None] = [None] * count
        batch_id = create_batch(count, submit=submit)
        self._batch_id = batch_id
        worker_count = max(1, min(workers, count))
        self.log(
            f"Batch {batch_id} started ({count} submission(s), submit={submit}, threads={worker_count})",
            "info",
        )

        if not headless:
            self.log("Keep the browser window open until each respondent finishes.", "info")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )

            queue: asyncio.Queue[int] = asyncio.Queue()
            for i in range(count):
                queue.put_nowait(i)

            async def _worker(worker_num: int) -> None:
                while not self._stop_requested:
                    try:
                        i = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    page = await context.new_page()
                    try:
                        result = await self.fill_one(
                            page, i, submit=submit, delay_ms=delay_ms, batch_id=batch_id
                        )
                        ordered_results[i] = result
                    except Exception as e:
                        msg = str(e)
                        if "closed" in msg.lower():
                            self.log(
                                f"Respondent {i + 1} failed: browser was closed. "
                                "Do not close the browser window during Quick Test.",
                                "error",
                            )
                        else:
                            self.log(f"Respondent {i + 1} failed on thread {worker_num}: {e}", "error")
                        err_result = {
                            "respondent": i + 1,
                            "status": "error",
                            "error": msg,
                            "batch_id": batch_id,
                        }
                        ordered_results[i] = err_result
                        if batch_id:
                            save_submission(
                                batch_id, i + 1, answers={}, status="error",
                                fields_filled=0, error=msg,
                            )
                    finally:
                        queue.task_done()
                        try:
                            await page.close()
                        except Exception:
                            pass

                    if between_submissions_ms > 0 and not self._stop_requested:
                        await asyncio.sleep(between_submissions_ms / 1000)

            worker_tasks = [
                asyncio.create_task(_worker(worker_num + 1))
                for worker_num in range(worker_count)
            ]
            await asyncio.gather(*worker_tasks)

            results = [r for r in ordered_results if r is not None]

            await browser.close()

        finish_batch(batch_id, results)
        self.log(f"Batch {batch_id} complete — review in Submissions tab", "success")
        return results
