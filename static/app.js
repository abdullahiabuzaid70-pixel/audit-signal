/* AuditSignal frontend */
const $ = (sel) => document.querySelector(sel);
const fmtN = (n) => "₦" + Number(n).toLocaleString("en-NG", { maximumFractionDigits: 0 });
const fmtN2 = (n) => "₦" + Number(n).toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const state = { signals: [], txnPage: 1, txnSearch: "" };

/* ---------- Load case ---------- */
$("#loadBtn").addEventListener("click", async () => {
  const btn = $("#loadBtn");
  btn.disabled = true; btn.textContent = "Running analysis…";
  try {
    const res = await fetch("/api/case/load", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (!res.ok) throw new Error(await res.text());
    $("#emptyState").classList.add("hidden");
    $("#app").classList.remove("hidden");
    await refreshAll();
  } catch (e) {
    alert("Failed to load case: " + e.message);
  } finally {
    btn.disabled = false; btn.textContent = "Load Demo Case";
  }
});

async function refreshAll() {
  const sum = await (await fetch("/api/summary")).json();
  renderSummary(sum);
  await loadSignals();
  loadTxns();
  loadLog();
}

/* ---------- Tabs ---------- */
document.querySelectorAll(".tab-btn").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.add("hidden"));
    $("#tab-" + b.dataset.tab).classList.remove("hidden");
  })
);

/* ---------- Dashboard ---------- */
function renderSummary(s) {
  const cards = [
    [s.txn_count.toLocaleString(), "Transactions", false],
    [s.signal_count, "Risk signals", false],
    [s.high_priority, "High priority", true],
    [s.unresolved, "Unresolved", true],
    [fmtN(s.total_affected), "Affected amount", false],
  ];
  $("#metrics").innerHTML = cards.map(([v, l, danger]) => `
    <div class="bg-white rounded-xl border border-slate-200 p-4 text-center">
      <div class="text-xl font-extrabold ${danger ? "text-red-600" : "text-slate-900"}">${v}</div>
      <div class="text-[10.5px] text-slate-500 uppercase tracking-wide">${l}</div>
    </div>`).join("");

  const maxC = Math.max(...Object.values(s.categories));
  $("#catBars").innerHTML = Object.entries(s.categories).sort((a, b) => b[1] - a[1]).map(([c, n]) => `
    <div>
      <div class="flex justify-between text-xs mb-1"><span class="font-medium">${c}</span><span class="text-slate-500">${n}</span></div>
      <div class="bar" style="width:${(n / maxC) * 100}%"></div>
    </div>`).join("");

  fetch("/api/signals").then((r) => r.json()).then((sigs) => {
    $("#topSignals").innerHTML = sigs.slice(0, 5).map((t) => `
      <div class="flex items-center gap-2 text-xs">
        <span class="font-extrabold text-slate-900">${t.score.toFixed(0)}</span>
        <span class="sev-${t.severity}">${t.severity.toUpperCase()}</span>
        <span class="font-semibold">${t.category}</span>
        <span class="text-slate-500">${fmtN(t.affected_amount)}</span>
      </div>`).join("");
  });

  const m = s.case_meta;
  $("#caseInfo").innerHTML = [
    ["Case", m.case_number], ["Taxpayer", `${m.taxpayer_name} — ${m.taxpayer_id}`],
    ["Period", `${m.period_start} to ${m.period_end}`],
    ["Rules", `VAT ${(s.rules.vat_rate * 100).toFixed(1)}% · WHT ${(s.rules.wht_rate * 100).toFixed(1)}% (configurable)`],
  ].map(([k, v]) => `<div><span class="text-slate-400">${k}:</span> ${v}</div>`).join("");
}

/* ---------- Risk queue ---------- */
async function loadSignals() {
  const sev = $("#sevFilter").value, cat = $("#catFilter").value, q = $("#queueSearch").value;
  const params = new URLSearchParams();
  if (sev) params.set("severity", sev);
  if (cat) params.set("category", cat);
  if (q) params.set("search", q);
  state.signals = await (await fetch("/api/signals?" + params)).json();
  renderQueue();
}

function renderQueue() {
  const cats = [...new Set(state.signals.map((s) => s.category))];
  const sel = $("#catFilter");
  if (sel.options.length <= 1) {
    sel.innerHTML = '<option value="">All categories</option>' + cats.map((c) => `<option>${c}</option>`).join("");
  }
  $("#signalList").innerHTML = state.signals.map((s) => `
    <div class="bg-white rounded-xl border border-slate-200 p-4" id="sig-${s.signal_id}">
      <div class="flex flex-wrap items-center gap-2">
        <span class="font-extrabold text-slate-900">${s.score.toFixed(0)}</span>
        <span class="sev-${s.severity}">${s.severity.toUpperCase()}</span>
        <span class="font-semibold text-sm">${s.category}</span>
        <span class="text-sm text-slate-500">${fmtN(s.affected_amount)}</span>
        <span class="ml-auto text-xs px-2 py-1 rounded bg-slate-100 ${s.status !== "Open" ? "text-blue-700 font-semibold" : "text-slate-500"}">${s.status}</span>
      </div>
      <p class="text-xs text-slate-600 mt-2">${s.explanation.slice(0, 170)}…</p>
      <button class="show-why mt-2 text-xs font-semibold text-blue-700 border border-blue-300 rounded-lg px-3 py-1.5 hover:bg-blue-50" data-id="${s.signal_id}">🔍 SHOW ME WHY</button>
      <div class="why-panel hidden mt-3 pl-3" id="why-${s.signal_id}"></div>
    </div>`).join("");
  document.querySelectorAll(".show-why").forEach((b) => b.addEventListener("click", () => toggleWhy(b.dataset.id)));
}

async function toggleWhy(id) {
  const panel = $("#why-" + id);
  if (!panel.classList.contains("hidden")) { panel.classList.add("hidden"); return; }
  panel.classList.remove("hidden");
  panel.innerHTML = '<p class="text-xs text-slate-400 py-4">Loading evidence…</p>';
  const s = await (await fetch("/api/signals/" + encodeURIComponent(id))).json();
  const bd = Object.entries(s.score_breakdown).map(([k, v]) => `<li><b>${k}:</b> ${v}</li>`).join("");
  const rows = s.records.map((r) => `
    <tr class="border-t border-slate-100">
      <td class="px-2 py-1.5">${r.txn_id}</td><td class="px-2 py-1.5">${r.date}</td>
      <td class="px-2 py-1.5">${r.invoice_no}</td><td class="px-2 py-1.5">${r.supplier_name}</td>
      <td class="px-2 py-1.5 text-right">${fmtN2(r.net_amount)}</td>
      <td class="px-2 py-1.5 text-right">${fmtN2(r.vat_amount)}</td>
      <td class="px-2 py-1.5 text-right">${fmtN2(r.wht_amount)}</td>
      <td class="px-2 py-1.5">${r.evidence_status}</td>
    </tr>`).join("");
  panel.innerHTML = `
    <div class="bg-slate-50 rounded-lg p-4 text-sm space-y-2">
      <p><b>What was detected:</b> ${s.explanation}</p>
      <p><b>Why it matters for review:</b> the records and calculation below are the full basis of this signal — nothing is inferred beyond them.</p>
      <p><b>Calculation / rule:</b> ${s.calculation}</p>
      <p><b>Evidence strength:</b> ${s.evidence_strength}</p>
      <div><b>Score breakdown (transparent, configurable):</b><ul class="list-disc ml-5 mt-1 text-xs space-y-0.5">${bd}</ul></div>
      <p><b>Suggested next review action:</b> ${s.suggested_action}</p>
      <p class="font-semibold mt-2">Affected records (${s.records.length}):</p>
      <div class="overflow-x-auto"><table class="w-full whitespace-nowrap">
        <thead><tr class="text-left text-[11px] text-slate-500 uppercase">
          <th class="px-2 py-1">Txn</th><th class="px-2 py-1">Date</th><th class="px-2 py-1">Invoice</th>
          <th class="px-2 py-1">Supplier</th><th class="px-2 py-1 text-right">Net</th>
          <th class="px-2 py-1 text-right">VAT</th><th class="px-2 py-1 text-right">WHT</th><th class="px-2 py-1">Evidence</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      <div class="mt-3 pt-3 border-t border-slate-200">
        <p class="font-semibold text-xs mb-1.5">Auditor decision</p>
        <div class="flex flex-wrap gap-2 items-center">
          <select id="dec-${s.signal_id}" class="text-sm border border-slate-300 rounded-lg px-2 py-1.5">
            ${["Confirmed","Not Substantiated","Request Evidence","Refer for Further Review","False Positive"].map(d => `<option>${d}</option>`).join("")}
          </select>
          <input id="rat-${s.signal_id}" placeholder="Rationale (required for the working paper)" class="text-sm border border-slate-300 rounded-lg px-2 py-1.5 flex-1 min-w-[200px]">
          <button class="record-dec bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold rounded-lg px-4 py-1.5" data-id="${s.signal_id}">Record decision</button>
        </div>
      </div>
    </div>`;
  panel.querySelector(".record-dec").addEventListener("click", () => recordDecision(s.signal_id));
}

async function recordDecision(id) {
  const decision = $("#dec-" + id).value, rationale = $("#rat-" + id).value;
  const res = await fetch("/api/decisions", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ signal_id: id, decision, rationale }),
  });
  if (res.ok) {
    await loadSignals(); loadLog();
    $("#why-" + id).classList.add("hidden");
  } else {
    const err = await res.json();
    alert(err.detail || "Could not record decision.");
  }
}

["#sevFilter", "#catFilter"].forEach((s) => $(s).addEventListener("change", loadSignals));
let qTimer; $("#queueSearch").addEventListener("input", () => { clearTimeout(qTimer); qTimer = setTimeout(loadSignals, 300); });

/* ---------- Transactions ---------- */
async function loadTxns() {
  const params = new URLSearchParams({ page: state.txnPage, per_page: 25, search: state.txnSearch });
  const d = await (await fetch("/api/transactions?" + params)).json();
  $("#txnInfo").textContent = `Showing ${d.rows.length} of ${d.total.toLocaleString()} records (page ${d.page})`;
  $("#txnTable").innerHTML = `
    <thead><tr class="text-left text-[11px] text-slate-500 uppercase bg-slate-50">
      ${["Txn","Date","Invoice","Supplier","Description","Net","VAT","WHT","Evidence"].map(h => `<th class="px-3 py-2">${h}</th>`).join("")}
    </tr></thead>
    <tbody>${d.rows.map((r) => `
      <tr class="border-t border-slate-100">
        <td class="px-3 py-1.5">${r.txn_id}</td><td class="px-3 py-1.5">${r.date}</td>
        <td class="px-3 py-1.5">${r.invoice_no}</td><td class="px-3 py-1.5">${r.supplier_name}</td>
        <td class="px-3 py-1.5">${r.description}</td>
        <td class="px-3 py-1.5 text-right">${fmtN2(r.net_amount)}</td>
        <td class="px-3 py-1.5 text-right">${fmtN2(r.vat_amount)}</td>
        <td class="px-3 py-1.5 text-right">${fmtN2(r.wht_amount)}</td>
        <td class="px-3 py-1.5">${r.evidence_status}</td>
      </tr>`).join("")}</tbody>`;
}
$("#txnPrev").addEventListener("click", () => { if (state.txnPage > 1) { state.txnPage--; loadTxns(); } });
$("#txnNext").addEventListener("click", () => { state.txnPage++; loadTxns(); });
let tTimer; $("#txnSearch").addEventListener("input", () => {
  clearTimeout(tTimer); tTimer = setTimeout(() => { state.txnPage = 1; state.txnSearch = $("#txnSearch").value; loadTxns(); }, 300);
});

/* ---------- Log ---------- */
async function loadLog() {
  const decs = await (await fetch("/api/decisions")).json();
  $("#decList").innerHTML = decs.length ? decs.map((d) => `
    <div class="bg-white rounded-xl border border-slate-200 p-3 text-sm">
      <b>${d.decision}</b> — ${d.signal_id} <span class="text-slate-400">(${d.timestamp})</span>
      <div class="text-xs text-slate-600 mt-1">Rationale: ${d.rationale}</div>
    </div>`).join("") : '<p class="text-xs text-slate-500">No decisions recorded yet.</p>';

  const log = await (await fetch("/api/audit-log")).json();
  $("#logTable").innerHTML = `
    <thead><tr class="text-left text-[11px] text-slate-500 uppercase bg-slate-50">
      <th class="px-3 py-2">Timestamp</th><th class="px-3 py-2">Action</th></tr></thead>
    <tbody>${log.map((e) => `<tr class="border-t border-slate-100"><td class="px-3 py-1.5">${e.timestamp}</td><td class="px-3 py-1.5">${e.action}</td></tr>`).join("")}</tbody>`;
}
