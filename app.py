"""
AuditSignal — Tax audit intelligence MVP (lean prototype).
Standalone demonstration using synthetic data only.
NOT an official Nigeria Revenue Service product; no affiliation claimed.
The auditor is the final decision-maker — this tool only prioritizes and explains.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from demo_data import generate_demo_case, CASE_META
from risk_engine import DEFAULT_RULES, DECISION_OPTIONS, run_all_checks
from report_generator import generate_report

st.set_page_config(page_title="AuditSignal — Audit Intelligence", page_icon="🔎", layout="wide")

# ---------- CSS ----------
st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton, div[data-testid="stToolbar"] { display: none !important; }
.stApp { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #F8FAFC; }
section[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E2E8F0; }
.as-hero { background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 60%, #1E293B 100%);
  padding: 18px 24px; border-radius: 14px; margin-bottom: 12px; box-shadow: 0 4px 20px rgba(15,23,42,.15); }
.as-hero h1 { color: #fff; font-size: 22px; font-weight: 800; margin: 0; letter-spacing: -.5px; }
.as-hero p { color: #94A3B8; font-size: 12px; margin: 4px 0 0 0; }
.as-disclaimer { background: #FEF3C7; border: 1px solid #F59E0B; color: #92400E;
  border-radius: 10px; padding: 8px 14px; font-size: 11.5px; margin-bottom: 14px; }
.metric-card { background: #fff; padding: 16px 12px; border-radius: 12px; border: 1px solid #E2E8F0; text-align: center; }
.metric-card .value { font-size: 20px; font-weight: 800; color: #0F172A; }
.metric-card .label { font-size: 10.5px; color: #64748B; text-transform: uppercase; letter-spacing: .5px; }
.sev-critical { background:#FEE2E2; color:#DC2626; padding:2px 9px; border-radius:6px; font-size:11px; font-weight:700; }
.sev-high { background:#FFEDD5; color:#EA580C; padding:2px 9px; border-radius:6px; font-size:11px; font-weight:700; }
.sev-medium { background:#FEF3C7; color:#CA8A04; padding:2px 9px; border-radius:6px; font-size:11px; font-weight:700; }
.sev-low { background:#DBEAFE; color:#2563EB; padding:2px 9px; border-radius:6px; font-size:11px; font-weight:700; }
</style>
""", unsafe_allow_html=True)

# ---------- Session state ----------
ss = st.session_state
if "case_loaded" not in ss:
    ss.case_loaded = False
    ss.txns = None
    ss.signals = []
    ss.decisions = {}
    ss.audit_log = []
    ss.rules = dict(DEFAULT_RULES)

def log_action(action):
    ss.audit_log.append({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": action})

# ---------- Hero ----------
st.markdown("""
<div class="as-hero">
  <h1>AuditSignal</h1>
  <p>Out of thousands of transactions — where should the auditor look first, and why.</p>
</div>
<div class="as-disclaimer">⚠️ Standalone prototype using <b>synthetic demo data only</b>. Not an official
Nigeria Revenue Service product — no government ownership, approval or affiliation is claimed or implied.
Risk signals are analytical exceptions requiring human review, never findings of fraud or law.</div>
""", unsafe_allow_html=True)

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("### Case")
    if not ss.case_loaded:
        if st.button("Load Demo Case", type="primary", use_container_width=True):
            with st.spinner("Generating 5,000 synthetic transactions and running the risk engine..."):
                ss.txns = generate_demo_case()
                ss.signals = run_all_checks(ss.txns, ss.rules)
                ss.case_loaded = True
                ss.decisions = {}
                ss.audit_log = []
                log_action("Demo case loaded and analysis run")
            st.rerun()
    else:
        st.success(f"Case {CASE_META['case_number']}\n{CASE_META['taxpayer_name']}")
        if st.button("Reset Case", use_container_width=True):
            ss.case_loaded = False
            st.rerun()

    st.markdown("---")
    st.markdown("### Rule Configuration")
    st.caption("Rates are configurable parameters — not legal truth. Subject to professional validation.")
    ss.rules["vat_rate"] = st.number_input("Expected VAT rate", value=ss.rules["vat_rate"],
                                           min_value=0.0, max_value=1.0, step=0.005, format="%.3f")
    ss.rules["wht_rate"] = st.number_input("Expected WHT rate", value=ss.rules["wht_rate"],
                                           min_value=0.0, max_value=1.0, step=0.005, format="%.3f")
    if ss.case_loaded and st.button("Re-run analysis with current rules", use_container_width=True):
        with st.spinner("Re-running risk engine..."):
            ss.signals = run_all_checks(ss.txns, ss.rules)
            log_action("Risk engine re-run with updated rule configuration")
        st.rerun()

if not ss.case_loaded:
    st.info("Load the demo case from the sidebar to begin. The demo generates a fictional taxpayer "
            "(Apex Meridian Trading Ltd.) with ~5,000 synthetic transactions and planted anomalies.")
    st.stop()

df = ss.txns
signals = ss.signals

# ---------- Tabs ----------
tab_dash, tab_queue, tab_txns, tab_log, tab_report = st.tabs(
    ["📊 Dashboard", "🎯 Risk Queue", "🧾 Transactions", "📝 Audit Log", "📄 Report"])

# ===== DASHBOARD =====
with tab_dash:
    decided = sum(1 for s in signals if s["signal_id"] in ss.decisions)
    open_sig = len(signals) - decided
    total_affected = sum(s["affected_amount"] for s in signals)
    high = sum(1 for s in signals if s["severity"] in ("high", "critical"))
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, (val, lab, danger) in zip([c1, c2, c3, c4, c5], [
            (f"{len(df):,}", "Transactions", False),
            (len(signals), "Risk signals", False),
            (high, "High priority", True),
            (open_sig, "Unresolved", True),
            (f"₦{total_affected/1e6:,.0f}m", "Affected amount", False)]):
        col.markdown(f"""<div class="metric-card {' ' if danger else ''}">
        <div class="value" style="{'color:#DC2626' if danger else ''}">{val}</div>
        <div class="label">{lab}</div></div>""", unsafe_allow_html=True)

    st.markdown("")
    cc1, cc2 = st.columns(2)
    with cc1:
        cat_counts = pd.Series([s["category"] for s in signals]).value_counts()
        fig = px.pie(names=cat_counts.index, values=cat_counts.values, hole=0.55,
                     title="Risk signals by category")
        fig.update_traces(textposition="inside", textinfo="label+value")
        fig.update_layout(margin=dict(t=50, b=10, l=10, r=10), height=320)
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        sev_df = pd.DataFrame([{"severity": s["severity"], "score": s["score"],
                                "amount": s["affected_amount"]} for s in signals])
        fig2 = px.scatter(sev_df, x="score", y="amount", color="severity", size="amount",
                          title="Signal priority map (score vs affected amount)",
                          color_discrete_map={"high": "#EA580C", "medium": "#CA8A04", "low": "#2563EB", "critical": "#DC2626"})
        fig2.update_layout(margin=dict(t=50, b=10, l=10, r=10), height=320)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### Top 5 priority signals")
    for s in signals[:5]:
        st.markdown(
            f"<span class='sev-{s['severity']}' style='margin-right:6px'>{s['severity'].upper()}</span>"
            f"<b>{s['category']}</b> — ₦{s['affected_amount']:,.0f} — {s['explanation'][:150]}...",
            unsafe_allow_html=True)

# ===== RISK QUEUE + SHOW ME WHY =====
with tab_queue:
    st.markdown("### Prioritized review queue")
    st.caption("Every signal is an exception requiring review — not an allegation. "
               "Open a signal and press SHOW ME WHY for the evidence.")
    f_sev = st.multiselect("Filter severity", ["critical", "high", "medium", "low"],
                           default=["high", "medium"])
    f_cat = st.multiselect("Filter category",
                           sorted(set(s["category"] for s in signals)),
                           default=None)
    search = st.text_input("Search signals", "")
    queue = [s for s in signals
             if s["severity"] in f_sev and (not f_cat or s["category"] in f_cat)
             and (not search or search.lower() in s["explanation"].lower())]
    st.caption(f"{len(queue)} signals shown (of {len(signals)})")

    for s in queue:
        status = ss.decisions.get(s["signal_id"], {}).get("decision", "Open")
        label = (f"{s['score']:.0f} | {s['category']} | ₦{s['affected_amount']:,.0f} "
                 f"| {s['severity'].upper()} | {status}")
        with st.expander(label):
            st.markdown(f"<span class='sev-{s['severity']}'>{s['severity'].upper()}</span> "
                        f"**{s['category']}** — signal `{s['signal_id']}` — reason code `{s['reason_code']}`",
                        unsafe_allow_html=True)
            if st.button("🔍 SHOW ME WHY", key=f"why_{s['signal_id']}"):
                ss[f"show_{s['signal_id']}"] = not ss.get(f"show_{s['signal_id']}", False)
            if ss.get(f"show_{s['signal_id']}", False):
                st.markdown("**What was detected:** " + s["explanation"])
                st.markdown("**Why it matters for review:** the records and calculation below are "
                            "the full basis of this signal — nothing is inferred beyond them.")
                st.markdown(f"**Calculation / rule:** {s['calculation']}")
                st.markdown("**Score breakdown (transparent, configurable):**")
                for comp, val in s["score_breakdown"].items():
                    st.markdown(f"- {comp}: {val}")
                st.markdown(f"**Evidence strength:** {s['evidence_strength']}")
                recs = s["records"][["txn_id", "date", "invoice_no", "supplier_name", "category",
                                     "net_amount", "vat_amount", "wht_amount", "evidence_status"]]
                st.markdown(f"**Affected records ({len(recs)}):**")
                st.dataframe(recs, use_container_width=True, height=min(40 + 35*len(recs), 300))
                st.markdown(f"**Suggested next review action:** {s['suggested_action']}")
                st.markdown("---")
                existing = ss.decisions.get(s["signal_id"], {})
                col1, col2 = st.columns([2, 1])
                with col1:
                    decision = st.selectbox("Auditor decision", DECISION_OPTIONS,
                                            key=f"dec_{s['signal_id']}",
                                            index=DECISION_OPTIONS.index(existing["decision"]) if existing else 0)
                    rationale = st.text_input("Rationale (required for the working paper)",
                                              value=existing.get("rationale", ""),
                                              key=f"rat_{s['signal_id']}")
                with col2:
                    st.markdown("&nbsp;")
                    if st.button("Record decision", type="primary",
                                 key=f"save_{s['signal_id']}"):
                        if not rationale.strip():
                            st.error("A rationale is required before recording the decision.")
                        else:
                            prev = existing.get("decision", "Open")
                            ss.decisions[s["signal_id"]] = {
                                "decision": decision, "rationale": rationale,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "category": s["category"],
                                "affected_amount": s["affected_amount"]}
                            log_action(f"Decision recorded on {s['signal_id']}: {decision} "
                                       f"(previous state: {prev})")
                            st.success("Decision recorded — visible in Audit Log and Report.")
                            st.rerun()

# ===== TRANSACTIONS =====
with tab_txns:
    st.markdown("### Transaction explorer")
    st.caption(f"{len(df):,} records. Use search to filter.")
    q = st.text_input("Search transactions (description, supplier, invoice)", "")
    view = df
    if q:
        mask = (df["description"].str.contains(q, case=False)
                | df["supplier_name"].str.contains(q, case=False)
                | df["invoice_no"].str.contains(q, case=False))
        view = df[mask]
    st.caption(f"Showing {len(view):,} of {len(df):,} records")
    st.dataframe(view, use_container_width=True, height=480)

# ===== AUDIT LOG =====
with tab_log:
    st.markdown("### Audit trail (append-only record of actions and decisions)")
    if not ss.audit_log:
        st.info("No actions recorded yet.")
    else:
        log_df = pd.DataFrame(ss.audit_log[::-1])
        st.dataframe(log_df, use_container_width=True, hide_index=True)
    st.divider()
    st.markdown("### Recorded decisions")
    if not ss.decisions:
        st.info("No decisions recorded yet.")
    else:
        dec_df = pd.DataFrame([{
            "signal_id": k, "category": v["category"], "decision": v["decision"],
            "rationale": v["rationale"], "timestamp": v["timestamp"],
            "affected_amount": v["affected_amount"]}
            for k, v in ss.decisions.items()])
        st.dataframe(dec_df, use_container_width=True, hide_index=True)

# ===== REPORT =====
with tab_report:
    st.markdown("### Working-paper / findings report")
    st.caption("Machine analysis and human-approved findings are clearly separated. "
               "The report includes the standard analytical-assistance disclaimer.")
    if st.button("Generate PDF report", type="primary"):
        decisions = list(ss.decisions.values())
        approved = [{"signal_id": k, **v} for k, v in ss.decisions.items()]
        pdf_bytes = generate_report(CASE_META, signals, approved, ss.audit_log)
        st.download_button("⬇️ Download report (PDF)", pdf_bytes,
                           f"AuditSignal_{CASE_META['case_number']}_report.pdf",
                           "application/pdf", use_container_width=True)
        log_action("Report generated")
