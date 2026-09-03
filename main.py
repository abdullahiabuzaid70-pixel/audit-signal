"""
AuditSignal — FastAPI backend + web UI.
Standalone prototype using synthetic demo data only.
Not an official Nigeria Revenue Service product; no affiliation claimed.
Risk signals are analytical exceptions requiring human review — never findings of law.
"""
import io
import json
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from demo_data import generate_demo_case, CASE_META
from risk_engine import DEFAULT_RULES, DECISION_OPTIONS, run_all_checks
from report_generator import generate_report

app = FastAPI(title="AuditSignal API", version="1.0")

_state = {
    "loaded": False,
    "df": None,
    "signals": [],
    "decisions": {},
    "audit_log": [],
    "rules": dict(DEFAULT_RULES),
}


def _log(action: str):
    _state["audit_log"].append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
    })


def _records(df: pd.DataFrame):
    d = df.copy()
    d["date"] = d["date"].astype(str)
    return json.loads(d.to_json(orient="records"))


def _signal_out(s, include_records=False):
    out = {k: v for k, v in s.items() if k != "records"}
    if include_records:
        out["records"] = _records(s["records"])
    return out


class RulesIn(BaseModel):
    vat_rate: float = DEFAULT_RULES["vat_rate"]
    wht_rate: float = DEFAULT_RULES["wht_rate"]


class DecisionIn(BaseModel):
    signal_id: str
    decision: str
    rationale: str


@app.post("/api/case/load")
def load_case(rules: RulesIn | None = None):
    """Generate the synthetic demo case and run the risk engine."""
    if rules:
        _state["rules"].update(rules.dict())
    _state["df"] = generate_demo_case()
    _state["signals"] = run_all_checks(_state["df"], _state["rules"])
    _state["decisions"] = {}
    _state["audit_log"] = []
    _state["loaded"] = True
    _log("Demo case loaded and analysis run")
    return summary()


@app.get("/api/summary")
def summary():
    if not _state["loaded"]:
        raise HTTPException(400, "No case loaded. POST /api/case/load first.")
    df, signals = _state["df"], _state["signals"]
    decided = sum(1 for s in signals if s["signal_id"] in _state["decisions"])
    return {
        "case_meta": CASE_META,
        "txn_count": len(df),
        "signal_count": len(signals),
        "high_priority": sum(1 for s in signals if s["severity"] in ("high", "critical")),
        "unresolved": len(signals) - decided,
        "total_affected": sum(s["affected_amount"] for s in signals),
        "categories": {c: sum(1 for s in signals if s["category"] == c)
                        for c in set(s["category"] for s in signals)},
        "rules": {k: _state["rules"][k] for k in ("vat_rate", "wht_rate")},
    }


@app.get("/api/signals")
def list_signals(category: str | None = None, severity: str | None = None, search: str | None = None):
    if not _state["loaded"]:
        raise HTTPException(400, "No case loaded.")
    out = []
    for s in _state["signals"]:
        if category and s["category"] != category:
            continue
        if severity and s["severity"] != severity:
            continue
        if search and search.lower() not in s["explanation"].lower():
            continue
        item = _signal_out(s)
        item["status"] = _state["decisions"].get(s["signal_id"], {}).get("decision", "Open")
        out.append(item)
    return out


@app.get("/api/signals/{signal_id}")
def get_signal(signal_id: str):
    """Full SHOW ME WHY detail: rule, records, calculation, score breakdown."""
    for s in _state["signals"]:
        if s["signal_id"] == signal_id:
            item = _signal_out(s, include_records=True)
            item["status"] = _state["decisions"].get(signal_id, {}).get("decision", "Open")
            return item
    raise HTTPException(404, f"Signal {signal_id} not found.")


@app.get("/api/transactions")
def list_transactions(page: int = 1, per_page: int = 25, search: str = ""):
    if not _state["loaded"]:
        raise HTTPException(400, "No case loaded.")
    df = _state["df"]
    if search:
        mask = (df["description"].str.contains(search, case=False)
                | df["supplier_name"].str.contains(search, case=False)
                | df["invoice_no"].str.contains(search, case=False))
        df = df[mask]
    total = len(df)
    start = (page - 1) * per_page
    rows = _records(df.iloc[start:start + per_page])
    return {"total": total, "page": page, "per_page": per_page, "rows": rows}


@app.post("/api/decisions")
def record_decision(dec: DecisionIn):
    if not _state["loaded"]:
        raise HTTPException(400, "No case loaded.")
    if not dec.rationale.strip():
        raise HTTPException(400, "A rationale is required before recording the decision.")
    if dec.decision not in DECISION_OPTIONS:
        raise HTTPException(400, f"decision must be one of {DECISION_OPTIONS}")
    sig = next((s for s in _state["signals"] if s["signal_id"] == dec.signal_id), None)
    if sig is None:
        raise HTTPException(404, f"Signal {dec.signal_id} not found.")
    prev = _state["decisions"].get(dec.signal_id, {}).get("decision", "Open")
    _state["decisions"][dec.signal_id] = {
        "decision": dec.decision,
        "rationale": dec.rationale.strip(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "category": sig["category"],
        "affected_amount": sig["affected_amount"],
    }
    _log(f"Decision recorded on {dec.signal_id}: {dec.decision} (previous state: {prev})")
    return {"ok": True, "previous": prev, "new": dec.decision}


@app.get("/api/decisions")
def list_decisions():
    return [{"signal_id": k, **v} for k, v in _state["decisions"].items()]


@app.get("/api/audit-log")
def audit_log():
    return list(reversed(_state["audit_log"]))


@app.get("/api/report")
def report():
    """Working-paper PDF. Machine analysis vs human-approved findings separated."""
    if not _state["loaded"]:
        raise HTTPException(400, "No case loaded.")
    approved = [{"signal_id": k, **v} for k, v in _state["decisions"].items()]
    pdf_bytes = generate_report(CASE_META, _state["signals"], approved, _state["audit_log"])
    _log("Report generated")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="AuditSignal_working_paper.pdf"'},
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")
