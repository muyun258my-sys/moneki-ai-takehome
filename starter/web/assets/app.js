const state = { meta: null, summary: null, latestTrace: null, sessionId: `web-${Date.now()}` };
const $ = (id) => document.getElementById(id);
const money = (value) => value == null ? "—" : `¥${Number(value).toLocaleString("zh-CN", {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
const count = (value) => value == null ? "—" : Number(value).toLocaleString("zh-CN");
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;", "'":"&#39;"}[char]));

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`请求失败（${response.status}）`);
  return response.json();
}

function query() {
  const params = new URLSearchParams({start: $("start-date").value, end: $("end-date").value});
  if ($("store-select").value) params.set("store_id", $("store-select").value);
  return params;
}

function showError(error) {
  $("error-text").textContent = error.message || String(error);
  $("error-notice").hidden = false;
}

function hideError() { $("error-notice").hidden = true; }

function setDefaults(period) {
  const end = period?.end || "2026-08-31";
  const start = period?.start || "2026-08-01";
  $("start-date").value = start.slice(0, 8) + "01";
  $("end-date").value = end;
  $("store-select").value = "";
  $("period-label").textContent = `数据范围 ${period?.start || start} — ${period?.end || end}`;
}

async function loadMeta() {
  state.meta = await api("/api/meta");
  setDefaults(state.meta.data_period);
  const select = $("store-select");
  select.innerHTML = '<option value="">全部门店</option>' + state.meta.stores.map((store) => `<option value="${esc(store.store_id)}">${esc(store.store_id)} · ${esc(store.store_name)}</option>`).join("");
  $("footer-health").textContent = `${state.meta.stores.length} 家门店 · ${state.meta.products.length} 个商品`;
}

async function loadDashboard() {
  hideError();
  const params = query();
  $("last-updated").textContent = "更新中…";
  try {
    const [summary, daily, products, quality, health] = await Promise.all([
      api(`/api/metrics/summary?${params}`), api(`/api/metrics/daily?${params}`),
      api(`/api/metrics/top-products?${params}&limit=10`), api("/api/data_quality"), api("/api/health")
    ]);
    state.summary = summary;
    renderSummary(summary); renderChart(daily.days || []); renderProducts(products.products || [], summary.net_revenue); renderQuality(quality.cleaning_report || {});
    $("service-status").textContent = health.llm_mode === "live" ? "服务在线 · Live LLM" : "服务在线 · Mock LLM";
    $("chat-mode").textContent = health.llm_mode === "live" ? "Live LLM" : "Mock 模式（无 Key）";
    $("last-updated").textContent = `刚刚更新 · ${new Date().toLocaleTimeString("zh-CN", {hour:"2-digit", minute:"2-digit"})}`;
  } catch (error) { showError(error); $("last-updated").textContent = "更新失败"; }
}

function renderSummary(data) {
  $("metric-revenue").textContent = money(data.net_revenue); $("metric-orders").textContent = count(data.orders); $("metric-aov").textContent = money(data.aov); $("metric-qty").textContent = count(data.qty);
  $("metric-revenue-foot").textContent = `退款 ${money(data.refund_amount)}`; $("metric-orders-foot").textContent = `筛选区间有效订单`; $("metric-refund").textContent = `退款 ${money(data.refund_amount)}`;
}

function renderChart(days) {
  const svg = $("trend-chart"); const width = 800; const height = 280; const pad = {left: 42, right: 16, top: 15, bottom: 30};
  const values = days.map((day) => Number(day.net_revenue) || 0); const max = Math.max(...values, 1); const min = Math.min(...values, 0); const range = max - min || 1;
  const x = (index) => pad.left + (days.length <= 1 ? 0 : index * (width - pad.left - pad.right) / (days.length - 1));
  const y = (value) => pad.top + (max - value) * (height - pad.top - pad.bottom) / range;
  const points = values.map((value, index) => `${x(index)},${y(value)}`).join(" ");
  const labels = [0, .5, 1].map((ratio) => { const value = min + range * (1 - ratio); return `<line class="chart-grid" x1="${pad.left}" x2="${width-pad.right}" y1="${y(value)}" y2="${y(value)}"/><text class="chart-label" x="0" y="${y(value)+4}">${value >= 1000 ? (value/1000).toFixed(0)+"k" : Math.round(value)}</text>`; }).join("");
  const tickStep = Math.max(1, Math.ceil(days.length / 6));
  const dateLabels = days.map((day, index) => index % tickStep === 0 ? `<text class="chart-label" text-anchor="middle" x="${x(index)}" y="${height-7}">${day.date.slice(5)}</text>` : "").join("");
  const area = `${pad.left},${height-pad.bottom} ${points} ${x(values.length-1)},${height-pad.bottom}`;
  const dots = days.map((day, index) => `<circle class="chart-point" cx="${x(index)}" cy="${y(values[index])}" r="3" data-index="${index}"/>`).join("");
  svg.innerHTML = `<defs><linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b7c70" stop-opacity=".18"/><stop offset="1" stop-color="#0b7c70" stop-opacity="0"/></linearGradient></defs>${labels}${dateLabels}<polygon class="chart-area" points="${area}"/><polyline class="chart-line" points="${points}"/>${dots}`;
  svg.querySelectorAll(".chart-point").forEach((dot) => dot.addEventListener("mouseenter", (event) => { const day = days[Number(event.target.dataset.index)]; const tip = $("chart-tooltip"); tip.innerHTML = `${esc(day.date)} · <b>${money(day.net_revenue)}</b>`; tip.style.left = `${event.target.cx.baseVal.value / width * 100}%`; tip.style.top = `${event.target.cy.baseVal.value / height * 100}%`; tip.hidden = false; }));
  svg.querySelectorAll(".chart-point").forEach((dot) => dot.addEventListener("mouseleave", () => $("chart-tooltip").hidden = true));
}

function renderProducts(products, total) {
  $("products-caption").textContent = `${products.length} 个商品 · 按净营业额`;
  $("products-table").innerHTML = products.length ? products.map((product, index) => { const share = total ? product.net_revenue / total : 0; return `<tr><td>${String(index + 1).padStart(2, "0")}</td><td>${esc(product.product_name || product.product_id)}<div class="muted">${esc(product.product_id)}</div></td><td>${esc(product.product_category || "—")}</td><td>${count(product.qty)}</td><td>${money(product.net_revenue)}</td><td><div class="bar-cell"><div class="bar"><i style="width:${Math.min(100, share * 100 * 4)}%"></i></div>${(share * 100).toFixed(1)}%</div></td></tr>`; }).join("") : '<tr><td colspan="6" class="empty-cell">区间内没有销售记录</td></tr>';
}

function renderQuality(report) {
  const raw = Number(report.raw_rows || 0); const kept = Number(report.kept_rows || 0); const rate = raw ? kept / raw : 0; const degree = Math.round(rate * 360);
  $("quality-ring").style.background = `conic-gradient(var(--teal) ${degree}deg, #edf1f2 ${degree}deg)`; $("quality-score").textContent = `${(rate * 100).toFixed(1)}%`; $("quality-summary").textContent = `${count(kept)} 行进入分析`; $("quality-detail").textContent = `原始 ${count(raw)} 行，剔除 ${count(raw-kept)} 行`;
  $("quality-badge").textContent = rate > .98 ? "质量良好" : "需要关注"; $("quality-list").innerHTML = Object.entries(report.removed || {}).filter(([key]) => !key.startsWith("note_")).map(([key, value]) => `<div class="quality-row"><span>${qualityLabel(key)}</span><span>${count(value)}</span></div>`).join("");
}

function qualityLabel(key) { return ({"1_unparseable_date":"日期无法解析","2_empty_amount":"金额为空","3_qty_le_zero":"数量无效","4_store_not_in_stores":"门店不存在","5_product_not_in_products":"商品不存在","6_duplicate_row":"重复行"}[key] || key); }

function openModal(id) { $(id).hidden = false; document.body.style.overflow = "hidden"; }
function closeModal(id) { $(id).hidden = true; document.body.style.overflow = ""; }

async function askQuestion(event) {
  event.preventDefault(); const input = $("chat-input"); const question = input.value.trim(); if (!question) return;
  const messages = $("chat-messages");
  const userBubble = document.createElement("div");
  userBubble.className = "chat-bubble user";
  userBubble.textContent = question;
  const pendingBubble = document.createElement("div");
  pendingBubble.className = "chat-bubble assistant pending";
  pendingBubble.textContent = "正在查数据…";
  messages.append(userBubble, pendingBubble);
  input.value = ""; messages.scrollTop = messages.scrollHeight;
  try {
    const result = await api("/api/chat", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({session_id:state.sessionId, question})});
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble assistant";
    bubble.innerHTML = esc(result.answer).replace(/\n/g,"<br>");
    if (result.trace_id) {
      const button = document.createElement("button");
      button.className = "text-button chat-trace-button";
      button.type = "button";
      button.dataset.traceId = result.trace_id;
      button.textContent = "查看 Trace";
      bubble.append(button);
    }
    pendingBubble.replaceWith(bubble);
    state.latestTrace = result.trace_id;
    $("open-chat-trace").disabled = !state.latestTrace;
  }
  catch (error) { pendingBubble.outerHTML = `<div class="chat-bubble assistant">${esc(error.message)}，请稍后重试。</div>`; }
  messages.scrollTop = messages.scrollHeight;
}

const traceCode = (value) => `<pre class="trace-code">${esc(typeof value === "string" ? value : JSON.stringify(value, null, 2))}</pre>`;

function renderTraceStep(step) {
  let detail = step.detail ? traceCode(step.detail) : "";
  if (step.step === "response" && step.detail?.answer) {
    const notes = (step.detail.notes || []).join("；");
    detail = `<div class="trace-label">${esc(notes || "实际返回给用户的内容")}</div>${traceCode(step.detail.answer)}`;
  }
  if (step.step === "search" && step.detail) {
    const search = step.detail;
    detail = `<div class="trace-label">检索查询：${esc(search.query)}</div>`
      + (search.hits || []).map((hit) => `<div class="trace-hit"><strong>${esc(hit.doc_id)} · ${esc(hit.chunk_id)}</strong><span>分数 ${esc(hit.score)}</span><p>${esc(hit.text)}</p></div>`).join("")
      + (search.filtered || []).map((hit) => `<div class="trace-hit filtered"><strong>${esc(hit.doc_id)} · ${esc(hit.chunk_id)}</strong><span>已过滤：${esc(hit.reason)}</span></div>`).join("");
  }
  return `<div class="trace-step"><div class="trace-step-head"><span>${esc(step.step === "response" ? "最终回答" : step.step)}</span><time>${step.took_ms == null ? "" : `${step.took_ms} ms`}</time></div>${detail}</div>`;
}

function renderLlmCall(call, index) {
  return `<div class="trace-step"><div class="trace-step-head"><span>模型调用 ${index + 1} · ${esc(call.model)}</span><time>${esc(call.took_ms)} ms</time></div>`
    + `<div class="trace-label">状态 ${esc(call.status ?? call.error ?? "未知")} · 结束原因 ${esc(call.finish_reason || "—")}</div>`
    + `<details class="trace-raw"><summary>最终提示词</summary>${traceCode(call.prompt || "")}</details>`
    + `<details class="trace-raw" open><summary>模型原始输出</summary>${traceCode(call.raw_response || {content: call.raw_content || "", reasoning_content: call.raw_reasoning || "", tool_calls: call.raw_tool_calls || []})}</details></div>`;
}

async function showTrace(traceId) {
  if (!traceId) return; openModal("trace-modal"); $("trace-summary").textContent = `Trace ID：${traceId} · 加载中…`; $("trace-body").innerHTML = "";
  try {
    const trace = await api(`/api/trace/${encodeURIComponent(traceId)}`);
    $("trace-summary").textContent = `Trace ID：${trace.trace_id} · ${trace.question} · 总耗时 ${trace.total_ms} ms`;
    const steps = trace.steps || [];
    $("trace-body").innerHTML = steps.filter((step) => step.step !== "response").map(renderTraceStep).join("")
      + (trace.llm_calls || []).map(renderLlmCall).join("")
      + (trace.errors || []).map((error) => `<div class="trace-error"><b>${esc(error.where)} · ${esc(error.type)}</b> · ${esc(error.message)}${traceCode(error.traceback || "")}</div>`).join("")
      + steps.filter((step) => step.step === "response").map(renderTraceStep).join("");
  }
  catch (error) { $("trace-summary").textContent = error.message; }
}

document.addEventListener("DOMContentLoaded", async () => {
  $("refresh-btn").addEventListener("click", loadDashboard); $("store-select").addEventListener("change", loadDashboard); $("start-date").addEventListener("change", loadDashboard); $("end-date").addEventListener("change", loadDashboard); $("reset-filters").addEventListener("click", () => { setDefaults(state.meta.data_period); loadDashboard(); }); $("dismiss-error").addEventListener("click", hideError); $("chat-form").addEventListener("submit", askQuestion);
  $("open-chat").addEventListener("click", () => openModal("chat-modal")); $("open-chat-nav").addEventListener("click", () => openModal("chat-modal")); $("open-chat-trace").addEventListener("click", () => showTrace(state.latestTrace)); $("open-trace-latest").addEventListener("click", () => showTrace(state.latestTrace)); $("quality-more").addEventListener("click", () => document.querySelector("#quality").scrollIntoView({behavior:"smooth"}));
  $("chat-messages").addEventListener("click", (event) => { const button = event.target.closest("[data-trace-id]"); if (button) showTrace(button.dataset.traceId); });
  document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => closeModal(button.dataset.close))); document.querySelectorAll(".modal-backdrop").forEach((backdrop) => backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeModal(backdrop.id); }));
  try { await loadMeta(); await loadDashboard(); } catch (error) { showError(error); }
});
