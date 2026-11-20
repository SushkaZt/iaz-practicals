// Логіка інтерфейсу: завантаження даних з API, таблиця, фільтри, сортування,
// реєстрація, зміна статусу, видалення та побудова аналітичних діаграм.

const API = "/api";
const STATUSES = JSON.parse(document.getElementById("statuses-data").textContent);
const PRIORITY_NAMES = { 1: "Високий", 2: "Середній", 3: "Низький" };

let allDocs = [];
let sortState = { column: "received_at", order: "desc" };

// ---------- Допоміжні функції ----------

// Екранування тексту перед вставкою в HTML (захист від XSS).
function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDate(iso) {
  return new Date(iso).toLocaleString("uk-UA", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function showMessage(el, text, type = "info") {
  el.textContent = text;
  el.className = `message ${text ? type : ""}`;
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Помилка сервера (${response.status})`);
  return data;
}

// ---------- Реєстр документів ----------

const tableBody = document.getElementById("table-body");
const listMessage = document.getElementById("list-message");
const rowCount = document.getElementById("row-count");
const filterText = document.getElementById("filter-text");
const filterSource = document.getElementById("filter-source");
const filterStatus = document.getElementById("filter-status");
const headers = document.querySelectorAll("#docs-table th[data-column]");

async function loadDocs() {
  try {
    allDocs = await request(`${API}/docs`);
    showMessage(listMessage, "");
    renderTable();
  } catch (err) {
    allDocs = [];
    renderTable();
    showMessage(listMessage, err.message, "error");
  }
}

function getVisibleDocs() {
  const text = filterText.value.trim().toLowerCase();
  const source = filterSource.value;
  const status = filterStatus.value;

  const filtered = allDocs.filter((doc) => {
    if (source && doc.source_type !== source) return false;
    if (status && doc.status !== status) return false;
    if (!text) return true;
    return Object.values(doc).some((v) => String(v ?? "").toLowerCase().includes(text));
  });

  const { column, order } = sortState;
  const dir = order === "asc" ? 1 : -1;
  return filtered.sort((a, b) => {
    let x = a[column] ?? "";
    let y = b[column] ?? "";
    if (column === "received_at") { x = new Date(x); y = new Date(y); }
    if (column === "priority") { x = Number(x); y = Number(y); }
    if (typeof x === "string") return x.localeCompare(y, "uk") * dir;
    return (x - y) * dir;
  });
}

function renderTable() {
  const docs = getVisibleDocs();
  rowCount.textContent = `(${docs.length} з ${allDocs.length})`;

  headers.forEach((th) => {
    th.classList.remove("sort-asc", "sort-desc");
    if (th.dataset.column === sortState.column) th.classList.add(`sort-${sortState.order}`);
  });

  if (docs.length === 0) {
    tableBody.innerHTML = `<tr><td colspan="8" class="empty">Документів не знайдено</td></tr>`;
    return;
  }

  tableBody.innerHTML = docs.map((doc) => `
    <tr data-id="${doc.id}">
      <td class="nowrap"><strong>${esc(doc.doc_reference)}</strong></td>
      <td class="nowrap">${formatDate(doc.received_at)}</td>
      <td>${esc(doc.source_type || "—")}</td>
      <td><span class="badge cls-${esc(doc.classification).toLowerCase()}">${esc(doc.classification)}</span></td>
      <td class="summary">${esc(doc.summary)}${doc.analyst_notes ? `<div class="notes">${esc(doc.analyst_notes)}</div>` : ""}</td>
      <td><span class="prio prio-${doc.priority}">${doc.priority} — ${PRIORITY_NAMES[doc.priority]}</span></td>
      <td>
        <select class="status-select" aria-label="Статус документа ${esc(doc.doc_reference)}">
          ${STATUSES.map((s) => `<option ${s === doc.status ? "selected" : ""}>${esc(s)}</option>`).join("")}
        </select>
      </td>
      <td><button class="btn-delete" type="button">Видалити</button></td>
    </tr>`).join("");
}

headers.forEach((th) => {
  th.addEventListener("click", () => {
    const column = th.dataset.column;
    sortState = sortState.column === column
      ? { column, order: sortState.order === "asc" ? "desc" : "asc" }
      : { column, order: "asc" };
    renderTable();
  });
});

[filterText, filterSource, filterStatus].forEach((el) => el.addEventListener("input", renderTable));

// Зміна статусу та видалення: один обробник на всю таблицю.
tableBody.addEventListener("change", async (event) => {
  if (!event.target.classList.contains("status-select")) return;
  const id = event.target.closest("tr").dataset.id;
  try {
    await request(`${API}/docs/${id}`, { method: "PATCH", body: JSON.stringify({ status: event.target.value }) });
    await refresh();
  } catch (err) {
    showMessage(listMessage, err.message, "error");
  }
});

tableBody.addEventListener("click", async (event) => {
  if (!event.target.classList.contains("btn-delete")) return;
  const row = event.target.closest("tr");
  const ref = row.querySelector("strong").textContent;
  if (!confirm(`Видалити документ ${ref}?`)) return;
  try {
    await request(`${API}/docs/${row.dataset.id}`, { method: "DELETE" });
    await refresh();
    showMessage(listMessage, `Документ ${ref} видалено`, "success");
  } catch (err) {
    showMessage(listMessage, err.message, "error");
  }
});

// ---------- Форма реєстрації ----------

const form = document.getElementById("doc-form");
const formMessage = document.getElementById("form-message");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form));

  if (!data.doc_reference.trim() || !data.summary.trim()) {
    showMessage(formMessage, "Заповніть номер і короткий зміст", "error");
    return;
  }
  data.priority = Number(data.priority);
  if (!data.received_at) delete data.received_at;

  try {
    const doc = await request(`${API}/docs`, { method: "POST", body: JSON.stringify(data) });
    showMessage(formMessage, `Документ ${doc.doc_reference} зареєстровано`, "success");
    form.reset();
    await refresh();
  } catch (err) {
    showMessage(formMessage, err.message, "error");
  }
});

// ---------- Аналітика ----------

function renderBars(containerId, items) {
  const el = document.getElementById(containerId);
  if (!items.length) { el.innerHTML = `<p class="muted">Немає даних</p>`; return; }
  const max = Math.max(...items.map((i) => i.count));
  el.innerHTML = items.map((i) => `
    <div class="bar-row">
      <span class="bar-label">${esc(i.label)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${(i.count / max) * 100}%"></span></span>
      <span class="bar-value">${i.count}</span>
    </div>`).join("");
}

function renderTimeline(items) {
  const el = document.getElementById("chart-day");
  const max = Math.max(1, ...items.map((i) => i.count));
  el.innerHTML = items.map((i) => `
    <div class="day" title="${esc(i.label)}: ${i.count}">
      <span class="day-value">${i.count || ""}</span>
      <span class="day-bar" style="height:${(i.count / max) * 100}%"></span>
      <span class="day-label">${esc(i.label)}</span>
    </div>`).join("");
}

async function loadStats() {
  try {
    const s = await request(`${API}/stats`);
    document.getElementById("kpi-total").textContent = s.summary.total;
    document.getElementById("kpi-week").textContent = s.summary.last_7_days;
    document.getElementById("kpi-open").textContent = s.summary.open_docs;
    document.getElementById("kpi-urgent").textContent = s.summary.urgent_open;
    renderBars("chart-source", s.by_source);
    renderBars("chart-classification", s.by_classification);
    renderBars("chart-priority", s.by_priority);
    renderBars("chart-status", s.by_status);
    renderTimeline(s.by_day);
  } catch (err) {
    showMessage(listMessage, err.message, "error");
  }
}

async function refresh() {
  await Promise.all([loadDocs(), loadStats()]);
}

refresh();
