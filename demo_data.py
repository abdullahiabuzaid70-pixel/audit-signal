"""
AuditSignal — Synthetic demo data generator.
Generates a fictional company case with clean records + planted anomalies.
NO REAL TAXPAYER DATA. All identifiers are fictional.
"""
import numpy as np
import pandas as pd

RNG_SEED = 42

SUPPLIERS = [
    ("SUP-001", "Meridian Logistics Ltd", False),
    ("SUP-002", "Zenith Office Supplies", False),
    ("SUP-003", "Apex Facilities Ltd", True),      # related party
    ("SUP-004", "Sahara IT Services", False),
    ("SUP-005", "Bluewave Consulting", False),
    ("SUP-006", "Kano Textiles Trading", False),
    ("SUP-007", "Lagoon Cleaning Services", False),
    ("SUP-008", "Anchor Leasing Ltd", True),        # related party
    ("SUP-009", "Prime Utilities Co", False),
    ("SUP-010", "Vertex Media Ltd", False),
    ("SUP-011", "Nimbus Cloud Hosting", False),
    ("SUP-012", "Downstream Freight Ltd", False),
]

CATEGORIES = [
    "consultancy", "logistics", "office supplies", "facilities",
    "it services", "cleaning", "utilities", "advertising",
    "hosting", "leasing", "freight", "textiles",
]

DESCRIPTIONS = {
    "consultancy": ["Advisory retainer", "Management consulting", "Project advisory"],
    "logistics": ["Freight charges", "Distribution services", "Haulage"],
    "office supplies": ["Stationery order", "Office consumables", "Print supplies"],
    "facilities": ["Maintenance works", "Facility repairs", "Generator servicing"],
    "it services": ["Software licence", "IT support", "System integration"],
    "cleaning": ["Cleaning services", "Janitorial retainer"],
    "utilities": ["Electricity bill", "Water charges", "Generator fuel"],
    "advertising": ["Media placement", "Campaign fees", "Brand design"],
    "hosting": ["Cloud subscription", "Data centre fees"],
    "leasing": ["Equipment lease", "Vehicle lease"],
    "freight": ["Customs clearing", "Freight forwarding"],
    "textiles": ["Fabric purchase", "Textile stock lot"],
}


def generate_demo_case(n_transactions=5000, seed=RNG_SEED):
    """Generate the fictional demo case 'Apex Meridian Trading Ltd'.

    Planted anomalies (scaled down from the 100k spec):
    - 8 duplicate invoice clusters (exact + near)
    - 12 VAT mismatches
    - 10 WHT mismatches
    - 6 unusual high-value transactions
    - 6 missing evidence records
    - related-party concentration via SUP-003 / SUP-008
    """
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2025-07-01")
    rows = []

    for i in range(n_transactions):
        sup_id, sup_name, related = SUPPLIERS[rng.integers(0, len(SUPPLIERS))]
        cat = CATEGORIES[rng.integers(0, len(CATEGORIES))]
        desc = DESCRIPTIONS[cat][rng.integers(0, len(DESCRIPTIONS[cat]))]
        # Log-normal amounts, typical range ~ NGN 50k - 2m
        net = float(np.round(rng.lognormal(mean=11.7, sigma=0.7), 2))
        date = start + pd.Timedelta(days=int(rng.integers(0, 365)))
        rows.append({
            "txn_id": f"TXN-{i+1:06d}",
            "invoice_no": f"INV-{100000+i}",
            "date": date,
            "supplier_id": sup_id,
            "supplier_name": sup_name,
            "related_party": related,
            "description": desc,
            "category": cat,
            "net_amount": net,
            "vat_amount": float(np.round(net * 0.075, 2)),
            "wht_amount": float(np.round(net * 0.05, 2)) if cat in (
                "consultancy", "it services", "advertising", "facilities", "cleaning") else 0.0,
            "ledger_account": f"EXP-{2000 + (i % 12)}",
            "source": "ERP export",
            "evidence_status": "linked",
        })

    df = pd.DataFrame(rows)
    df["gross_amount"] = np.round(df["net_amount"] + df["vat_amount"] - df["wht_amount"], 2)

    # ---------- PLANTED ANOMALIES ----------
    # 1. Duplicate invoice clusters (exact + near-duplicate same amount/date)
    for c in range(8):
        idx = int(rng.integers(0, n_transactions))
        base = df.iloc[idx]
        clone = base.copy()
        clone["txn_id"] = f"TXN-D{c+1:04d}"
        if c < 4:
            pass  # exact duplicate invoice_no
        else:
            clone["invoice_no"] = base["invoice_no"][:-1] + str(int(base["invoice_no"][-1]) + 1)  # near
        df = pd.concat([df, pd.DataFrame([clone])], ignore_index=True)

    # 2. VAT mismatches (undercharged / zero VAT on large invoices)
    for c in range(12):
        idx = int(rng.integers(0, n_transactions))
        if df.at[idx, "net_amount"] > 100000:
            df.at[idx, "vat_amount"] = float(np.round(df.at[idx, "net_amount"] * 0.02, 2))  # 2% instead of 7.5%

    # 3. WHT mismatches (missing WHT on service categories)
    for c in range(10):
        idx = int(rng.integers(0, n_transactions))
        if df.at[idx, "category"] in ("consultancy", "it services", "advertising"):
            df.at[idx, "wht_amount"] = 0.0

    # 4. Unusual high-value transactions (extreme outliers)
    for c in range(6):
        idx = int(rng.integers(0, n_transactions))
        df.at[idx, "net_amount"] = float(rng.integers(25_000_000, 60_000_000))
        df.at[idx, "vat_amount"] = float(np.round(df.at[idx, "net_amount"] * 0.075, 2))

    # 5. Missing supporting evidence
    missing_idx = rng.choice(n_transactions, size=6, replace=False)
    for idx in missing_idx:
        df.at[int(idx), "evidence_status"] = "missing"

    df["gross_amount"] = np.round(df["net_amount"] + df["vat_amount"] - df["wht_amount"], 2)
    df = df.sort_values("date").reset_index(drop=True)
    return df


CASE_META = {
    "case_number": "AC-2026-0001",
    "taxpayer_name": "Apex Meridian Trading Ltd.",
    "taxpayer_id": "TP-DEMO-0000001 (fictional)",
    "period_start": "2025-07-01",
    "period_end": "2026-06-30",
    "currency": "NGN",
}
