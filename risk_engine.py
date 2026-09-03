"""
AuditSignal — Risk engine.
Deterministic audit checks + transparent risk scoring.
Every signal carries its own explanation, affected records and calculation.
The engine NEVER labels anything as fraud — only "risk signal" / "requires review".
"""
import pandas as pd
import numpy as np

DECISION_OPTIONS = [
    "Confirmed", "Not Substantiated", "Request Evidence",
    "Refer for Further Review", "False Positive",
]

DEFAULT_RULES = {
    "vat_rate": 0.075,          # configurable — not legal truth
    "wht_rate": 0.05,           # configurable — not legal truth
    "wht_categories": ["consultancy", "it services", "advertising", "facilities", "cleaning"],
    "outlier_sigma": 3.0,
    "round_number_floor": 1_000_000,
    "amount_weight": 0.35,
    "severity_weight": 0.30,
    "evidence_weight": 0.20,
    "frequency_weight": 0.15,
}


def _score_signal(severity, affected_amount, evidence_strength, repeat_count, rules):
    """Transparent composite score, 0-100, with component breakdown."""
    amt_component = min(affected_amount / 50_000_000, 1.0) * 100
    sev_component = {"critical": 100, "high": 75, "medium": 50, "low": 25}[severity]
    ev_component = {"strong": 100, "moderate": 60, "weak": 30}[evidence_strength]
    freq_component = min(repeat_count / 10, 1.0) * 100
    score = (
        rules["amount_weight"] * amt_component
        + rules["severity_weight"] * sev_component
        + rules["evidence_weight"] * ev_component
        + rules["frequency_weight"] * freq_component
    )
    return round(score, 1), {
        "amount component": f"{amt_component:.0f}/100 (affected NGN {affected_amount:,.0f})",
        "severity component": f"{sev_component:.0f}/100 ({severity})",
        "evidence component": f"{ev_component:.0f}/100 ({evidence_strength})",
        "frequency component": f"{freq_component:.0f}/100 ({repeat_count} linked records)",
        "weights": f"amount {rules['amount_weight']:.0%} / severity {rules['severity_weight']:.0%} / evidence {rules['evidence_weight']:.0%} / frequency {rules['frequency_weight']:.0%}",
    }


def _make_signal(category, severity, evidence_strength, affected_amount, reason_code,
                 explanation, records, calculation, suggested_action, rules):
    score, breakdown = _score_signal(severity, affected_amount, evidence_strength,
                                     len(records), rules)
    return {
        "signal_id": f"SIG-{category[:3].upper()}-{reason_code}",
        "category": category,
        "severity": severity,
        "score": score,
        "evidence_strength": evidence_strength,
        "affected_amount": affected_amount,
        "reason_code": reason_code,
        "explanation": explanation,
        "records": records,
        "calculation": calculation,
        "suggested_action": suggested_action,
        "score_breakdown": breakdown,
        "status": "Open",
    }


def check_duplicate_invoices(df, rules):
    """Exact duplicates on invoice_no + supplier; deterministic."""
    signals = []
    dup_groups = df.groupby(["invoice_no", "supplier_id"]).size()
    dup_keys = dup_groups[dup_groups > 1]
    for (inv, sup) in dup_keys.index:
        recs = df[(df["invoice_no"] == inv) & (df["supplier_id"] == sup)]
        amount = float(recs["net_amount"].sum() - recs["net_amount"].iloc[0])  # extra payments
        signals.append(_make_signal(
            "Duplicate Invoice", "high", "strong", max(amount, 0), "DUP-EXACT",
            f"Invoice {inv} to supplier {sup} appears {len(recs)} times. The records share the same "
            f"invoice number, supplier, date and amount, which may indicate a repeated payment requiring review.",
            recs, f"{len(recs)} records share invoice {inv}; combined net NGN {recs['net_amount'].sum():,.2f}",
            "Confirm with accounts payable whether the invoice was paid more than once; request payment vouchers.",
            rules))
    return signals


def check_vat_mismatch(df, rules):
    """Expected VAT from configurable rule table vs supplied VAT values."""
    signals = []
    rate = rules["vat_rate"]
    df2 = df[df["net_amount"] > 0].copy()
    df2["expected_vat"] = (df2["net_amount"] * rate).round(2)
    df2["variance"] = (df2["vat_amount"] - df2["expected_vat"]).abs()
    mask = (df2["variance"] > (df2["expected_vat"] * 0.5)) & (df2["expected_vat"] > 5000)
    for _, r in df2[mask].iterrows():
        signals.append(_make_signal(
            "VAT Mismatch", "medium", "strong", float(r["variance"]), "VAT-LOW",
            f"Transaction {r['txn_id']} (invoice {r['invoice_no']}) shows VAT of NGN {r['vat_amount']:,.2f} "
            f"against an expected NGN {r['expected_vat']:,.2f} at the configured {rate:.1%} rate. "
            "This is a potential discrepancy requiring review.",
            df[df["txn_id"] == r["txn_id"]],
            f"Expected = net NGN {r['net_amount']:,.2f} x {rate:.1%} = NGN {r['expected_vat']:,.2f}; "
            f"supplied VAT = NGN {r['vat_amount']:,.2f}; variance = NGN {r['variance']:,.2f}",
            "Request the tax invoice to verify the VAT actually charged by the supplier.",
            rules))
    return signals


def check_wht_mismatch(df, rules):
    """Configured expected WHT treatment vs transaction data."""
    signals = []
    rate = rules["wht_rate"]
    cats = set(rules["wht_categories"])
    df2 = df[(df["category"].isin(cats)) & (df["net_amount"] > 100000)].copy()
    df2["expected_wht"] = (df2["net_amount"] * rate).round(2)
    df2["gap"] = (df2["expected_wht"] - df2["wht_amount"]).abs()
    mask = (df2["gap"] > (df2["expected_wht"] * 0.5))
    for _, r in df2[mask].iterrows():
        signals.append(_make_signal(
            "WHT Mismatch", "medium", "moderate", float(r["gap"]), "WHT-MISS",
            f"Transaction {r['txn_id']} (invoice {r['invoice_no']}, category '{r['category']}') shows "
            f"WHT of NGN {r['wht_amount']:,.2f} where the configured treatment expects NGN {r['expected_wht']:,.2f}. "
            "Withholding treatment is configurable and subject to professional validation.",
            df[df["txn_id"] == r["txn_id"]],
            f"Expected = net NGN {r['net_amount']:,.2f} x {rate:.1%} = NGN {r['expected_wht']:,.2f}; "
            f"supplied WHT = NGN {r['wht_amount']:,.2f}; gap = NGN {r['gap']:,.2f}",
            "Verify whether withholding was deducted and remitted; request WHT credit notes.",
            rules))
    return signals


def check_unusual_transactions(df, rules):
    """Transparent statistical outliers — never labelled fraudulent."""
    signals = []
    mean, std = df["net_amount"].mean(), df["net_amount"].std()
    thresh = mean + rules["outlier_sigma"] * std
    out = df[df["net_amount"] > thresh].copy()
    for _, r in out.iterrows():
        sigmas = (r["net_amount"] - mean) / std
        signals.append(_make_signal(
            "Unusual Transaction", "medium", "moderate", float(r["net_amount"]), "OUTLIER-AMT",
            f"Transaction {r['txn_id']} (invoice {r['invoice_no']}) is NGN {r['net_amount']:,.2f} — "
            f"{sigmas:.1f} standard deviations above the case baseline. This is a statistical exception, "
            "not an allegation; it warrants review for supporting evidence.",
            df[df["txn_id"] == r["txn_id"]],
            f"Case baseline mean NGN {mean:,.2f}, std NGN {std:,.2f}; threshold = mean + "
            f"{rules['outlier_sigma']}σ = NGN {thresh:,.2f}",
            "Request contract / approval documentation supporting the transaction size.",
            rules))
    # Round-number payments
    floor = rules["round_number_floor"]
    rnd = df[(df["net_amount"] >= floor) & (df["net_amount"] % 1_000_000 == 0)]
    for _, r in rnd.iterrows():
        signals.append(_make_signal(
            "Unusual Transaction", "low", "weak", float(r["net_amount"]), "ROUND-NUM",
            f"Transaction {r['txn_id']} is an exact multiple of NGN 1,000,000. Exact round amounts are a "
            "recognised review pattern; on its own this is weak evidence requiring corroboration.",
            df[df["txn_id"] == r["txn_id"]],
            f"NGN {r['net_amount']:,.2f} is exactly {r['net_amount']/1_000_000:.0f}x NGN 1,000,000",
            "Review whether the pricing is supported by an underlying contract.",
            rules))
    return signals


def check_missing_evidence(df, rules):
    """Transactions whose required supporting-document link is absent."""
    signals = []
    miss = df[df["evidence_status"] == "missing"]
    for _, r in miss.iterrows():
        signals.append(_make_signal(
            "Missing Evidence", "medium", "strong", float(r["net_amount"]), "EVID-MISS",
            f"Transaction {r['txn_id']} (invoice {r['invoice_no']}, NGN {r['net_amount']:,.2f}) has no linked "
            "supporting document. The required evidence relationship is absent or failed validation.",
            df[df["txn_id"] == r["txn_id"]],
            f"evidence_status = 'missing' for NGN {r['net_amount']:,.2f} in category '{r['category']}'",
            "Request the invoice / receipt from the taxpayer.",
            rules))
    return signals


def check_related_party(df, rules):
    """Concentration patterns involving designated related parties (from demo metadata)."""
    signals = []
    rp = df[df["related_party"]]
    for sup_id, grp in rp.groupby("supplier_id"):
        sup_name = grp["supplier_name"].iloc[0]
        total = float(grp["net_amount"].sum())
        share = total / float(df["net_amount"].sum())
        if share > 0.15:
            signals.append(_make_signal(
                "Related-Party Anomaly", "medium", "moderate", total, "RP-CONC",
                f"Spend with related party '{sup_name}' ({sup_id}) totals NGN {total:,.2f} — "
                f"{share:.1%} of the case population across {len(grp)} transactions. Concentration with a "
                "designated related party warrants review of pricing and arm's-length support. The related-party "
                "designation comes from the supplied demo metadata.",
                grp, f"NGN {total:,.2f} across {len(grp)} transactions = {share:.1%} of case spend",
                "Review transfer-pricing documentation and arm's-length support for the related-party pricing.",
                rules))
    return signals


def run_all_checks(df, rules):
    """Run the full engine; returns list of signals sorted by score desc."""
    signals = []
    signals += check_duplicate_invoices(df, rules)
    signals += check_vat_mismatch(df, rules)
    signals += check_wht_mismatch(df, rules)
    signals += check_unusual_transactions(df, rules)
    signals += check_missing_evidence(df, rules)
    signals += check_related_party(df, rules)
    # make ids unique
    for i, s in enumerate(signals):
        s["signal_id"] = f"{s['signal_id']}-{i+1:03d}"
    signals.sort(key=lambda s: s["score"], reverse=True)
    return signals
