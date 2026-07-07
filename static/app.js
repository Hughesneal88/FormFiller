const state = {
  schema: null,
  questions: [],
  guidelines: {},
  running: false,
  ws: null,
  batches: [],
  selectedBatch: null,
  questionMap: {},
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function timeNow() {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

function addLog(message, level = "info") {
  const console = $("#logConsole");
  const first = console.querySelector(".muted");
  if (first) first.remove();

  const line = document.createElement("div");
  line.className = `log-line ${level}`;
  line.innerHTML = `<span class="log-time">${timeNow()}</span>${escapeHtml(message)}`;
  console.appendChild(line);
  console.scrollTop = console.scrollHeight;
}

function escapeHtml(str) {
  if (str == null) return "";
  const d = document.createElement("div");
  d.textContent = String(str);
  return d.innerHTML;
}

function formatValue(v) {
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function getSubmissionCount() {
  return Math.min(100, Math.max(1, parseInt($("#inputCount").value, 10) || 1));
}

function updateCountUI() {
  const count = getSubmissionCount();
  $("#startCountLabel").textContent = count;
  $$(".preset-btn").forEach((btn) => {
    btn.classList.toggle("active", parseInt(btn.dataset.count, 10) === count);
  });
}

function setSubmissionCount(count) {
  $("#inputCount").value = Math.min(100, Math.max(1, count));
  updateCountUI();
}

function setRunning(running) {
  state.running = running;
  $("#statStatus").textContent = running ? "Running" : "Idle";
  $("#btnStart").disabled = running;
  $("#btnStop").disabled = !running;
  $("#btnQuickTest").disabled = running;
  const pill = $("#connectionStatus");
  pill.classList.toggle("running", running);
}

function switchTab(tab) {
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $$(".panel").forEach((p) => p.classList.remove("active"));
  $(`#panel-${tab}`).classList.add("active");
}

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  state.ws = ws;

  ws.onopen = () => {
    $("#connectionStatus").className = "status-pill connected";
    $("#connectionStatus").innerHTML = '<span class="dot"></span> Connected';
    addLog("WebSocket connected", "success");
  };

  ws.onclose = () => {
    $("#connectionStatus").className = "status-pill";
    $("#connectionStatus").innerHTML = '<span class="dot"></span> Disconnected';
    setTimeout(connectWebSocket, 3000);
  };

  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === "log") addLog(data.message, data.level);
    if (data.type === "status") setRunning(data.running);
    if (data.type === "complete") {
      setRunning(false);
      addLog(`Batch complete — ${data.results?.length || 0} result(s)`, "success");
      loadSubmissions();
      switchTab("submissions");
    }
    if (data.type === "error") {
      setRunning(false);
      addLog(data.message, "error");
    }
  };
}

async function loadSchema() {
  const res = await fetch("/api/schema");
  const data = await res.json();
  state.schema = data.schema;
  state.questions = data.questions;
  state.questionMap = Object.fromEntries(data.questions.map((q) => [q.id, q]));

  $("#surveyTitle").textContent = data.schema.title;
  $("#statQuestions").textContent = data.question_count;
  $("#statStrategy").textContent = "Guided";

  renderSections(data.schema);
  renderQuestions(data.questions);
}

async function loadGuidelines() {
  const res = await fetch("/api/guidelines");
  state.guidelines = await res.json();
  $("#guidelinesEditor").value = JSON.stringify(state.guidelines, null, 2);
}

async function loadSubmissions() {
  const res = await fetch("/api/submissions");
  const data = await res.json();
  state.batches = data.batches || [];
  const total = state.batches.reduce((s, b) => s + (b.completed || 0), 0);
  $("#statSubmissions").textContent = total;
  renderBatchList();
}

function renderBatchList() {
  const list = $("#batchList");
  if (!state.batches.length) {
    list.innerHTML = '<p class="muted-text">No submissions yet. Run a test batch first.</p>';
    return;
  }

  list.innerHTML = state.batches
    .map(
      (b) => `
    <div class="batch-item ${state.selectedBatch === b.batch_id ? "active" : ""}" data-batch="${escapeHtml(b.batch_id)}">
      <div class="batch-id">${escapeHtml(b.batch_id)}</div>
      <div class="batch-meta">
        ${b.completed || 0} / ${b.planned_count || "?"} ·
        <span class="status-badge ${b.submit_enabled ? "submitted" : "preview"}">${b.submit_enabled ? "submit on" : "dry run"}</span>
      </div>
    </div>`
    )
    .join("");

  list.querySelectorAll(".batch-item").forEach((el) => {
    el.addEventListener("click", () => loadBatchDetail(el.dataset.batch));
  });
}

async function loadBatchDetail(batchId) {
  state.selectedBatch = batchId;
  renderBatchList();

  const res = await fetch(`/api/submissions/${batchId}`);
  const batch = await res.json();

  $("#detailTitle").textContent = `Batch ${batchId}`;
  const detail = $("#submissionDetail");

  if (!batch.submissions?.length) {
    detail.innerHTML = '<p class="muted-text">No respondents in this batch yet.</p>';
    return;
  }

  const chips = batch.submissions
    .map(
      (s) =>
        `<span class="respondent-chip" data-resp="${s.respondent}">#${s.respondent} ${escapeHtml(s.meta?.name || "")}</span>`
    )
    .join("");

  detail.innerHTML = `<div style="margin-bottom:1rem">${chips}</div><div id="respondentAnswers"></div>`;

  detail.querySelectorAll(".respondent-chip").forEach((chip) => {
    chip.addEventListener("click", () => showRespondent(batchId, parseInt(chip.dataset.resp, 10)));
  });

  showRespondent(batchId, batch.submissions[0].respondent);
}

async function showRespondent(batchId, respondent) {
  $$(".respondent-chip").forEach((c) =>
    c.classList.toggle("active", parseInt(c.dataset.resp, 10) === respondent)
  );

  const res = await fetch(`/api/submissions/${batchId}/${respondent}`);
  const sub = await res.json();

  const statusClass = sub.status?.includes("submitted") ? "submitted" : sub.status?.includes("error") ? "error" : "preview";
  let html = `
    <p><span class="status-badge ${statusClass}">${escapeHtml(sub.status)}</span>
    · ${sub.fields_filled} fields · ${escapeHtml(sub.timestamp || "")}</p>`;

  if (sub.screenshot) {
    html += `<img class="screenshot-preview" src="/submissions/${batchId}/${sub.screenshot}" alt="Form screenshot" />`;
  }

  const rows = Object.entries(sub.labeled_answers || {})
    .sort((a, b) => (a[1].number || 0) - (b[1].number || 0))
    .map(
      ([, v]) => `
    <div class="answer-row">
      <span class="q-num">Q${v.number || "?"}</span>
      <div>
        <div>${escapeHtml(v.label)}</div>
        <div class="q-val">${escapeHtml(formatValue(v.value))}</div>
      </div>
    </div>`
    )
    .join("");

  $("#respondentAnswers").innerHTML = html;
}

function renderPreviewResponses(responses) {
  const container = $("#previewResults");
  container.innerHTML = responses
    .map((r, i) => {
      const meta = r._meta || {};
      const highlights = [
        ["Name", r.q1],
        ["Phone", r.q2],
        ["Age", r.q4],
        ["Town", r.q9],
        ["Experience", r.q17],
        ["Employment", r.q18],
        ["Weekly catch", r.q50],
        ["Monthly income", r.q52],
        ["Q79", r.q79],
      ];
      return `
      <div class="preview-card-item">
        <h4>Respondent #${i + 1} — ${escapeHtml(meta.name || r.q1)} (age ${meta.age || r.q4})</h4>
        <div class="preview-summary">
          ${highlights.map(([k, v]) => `<div class="preview-field"><strong>${k}</strong>${escapeHtml(formatValue(v))}</div>`).join("")}
        </div>
      </div>`;
    })
    .join("");
}

async function previewAnswers(count = 5) {
  addLog(`Generating ${count} preview profile(s)…`, "info");
  const res = await fetch("/api/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ count }),
  });
  const data = await res.json();
  if (data.ok) {
    renderPreviewResponses(data.responses);
    switchTab("submissions");
    addLog(`Preview ready — ${count} profile(s) generated`, "success");
  }
}

function renderSections(schema) {
  const container = $("#sectionsOverview");
  container.innerHTML = schema.sections
    .map(
      (s) => `
    <div class="section-chip">
      <h4>Section ${s.id}</h4>
      <p>${escapeHtml(s.title)}</p>
      <div class="count">${s.questions.length} question(s)</div>
    </div>`
    )
    .join("");
}

function renderQuestions(questions, filter = "") {
  const list = $("#questionsList");
  const q = filter.toLowerCase();
  const filtered = questions.filter(
    (item) =>
      !q ||
      item.label.toLowerCase().includes(q) ||
      String(item.number).includes(q) ||
      item.section.toLowerCase().includes(q)
  );

  list.innerHTML = filtered
    .map(
      (item) => `
    <div class="question-item">
      <span class="q-number">Q${item.number}</span>
      <div>
        <div class="q-label">${escapeHtml(item.label)}</div>
        <div class="q-section">${escapeHtml(item.section)}</div>
      </div>
      <div class="q-meta">
        <span class="q-type">${item.type.replace("_", " ")}</span>
        ${item.required ? '<span class="q-required">Required</span>' : ""}
      </div>
    </div>`
    )
    .join("");
}

function initTabs() {
  $$(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
}

async function startRun(overrides = {}) {
  const count = overrides.count ?? getSubmissionCount();
  const config = {
    count,
    headless: overrides.headless ?? $("#inputHeadless").checked,
    submit: overrides.submit ?? $("#inputSubmit").checked,
    delay_ms: parseInt($("#inputDelay").value, 10) || 200,
    between_ms: parseInt($("#inputBetween").value, 10) || 2000,
  };

  setSubmissionCount(count);
  addLog(`Starting batch: ${config.count} submission(s), submit=${config.submit}`, "info");
  setRunning(true);

  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  const data = await res.json();
  if (!data.ok) {
    addLog(data.error || "Failed to start", "error");
    setRunning(false);
  }
}

async function stopRun() {
  await fetch("/api/stop", { method: "POST" });
  addLog("Stop requested", "warn");
}

document.addEventListener("DOMContentLoaded", async () => {
  initTabs();
  connectWebSocket();
  await loadSchema();
  await loadGuidelines();
  await loadSubmissions();

  $("#btnStart").addEventListener("click", () => startRun());
  $("#btnStop").addEventListener("click", stopRun);
  $("#btnPreview").addEventListener("click", () => previewAnswers(getSubmissionCount()));
  $("#btnQuickTest").addEventListener("click", () =>
    startRun({ headless: false, submit: false })
  );
  $("#inputCount").addEventListener("input", updateCountUI);
  $("#inputCount").addEventListener("change", updateCountUI);
  $$(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => setSubmissionCount(parseInt(btn.dataset.count, 10)));
  });
  updateCountUI();
  $("#btnRefreshSubmissions").addEventListener("click", loadSubmissions);
  $("#btnClearLogs").addEventListener("click", () => {
    $("#logConsole").innerHTML = '<div class="log-line muted">Log cleared</div>';
  });
  $("#questionSearch").addEventListener("input", (e) => {
    renderQuestions(state.questions, e.target.value);
  });
});
