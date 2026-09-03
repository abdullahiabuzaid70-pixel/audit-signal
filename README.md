# AuditSignal

Tax audit intelligence MVP (lean prototype).

Out of thousands of transactions — where should the auditor look first, and why?

**Standalone prototype using synthetic demo data only.** Not an official Nigeria Revenue
Service product; no government ownership, approval or affiliation is claimed or implied.
Risk signals are analytical exceptions requiring human review — never findings of fraud or law.

## Features
- Demo case: fictional taxpayer (Apex Meridian Trading Ltd.), ~5,000 synthetic transactions
  with planted anomalies
- 6 deterministic risk checks: duplicate invoices, VAT mismatch, WHT mismatch,
  unusual transactions, missing evidence, related-party concentration
- Transparent, configurable risk scoring with reason codes and score breakdowns
- **SHOW ME WHY**: every signal exposes its rule, affected records, calculation and
  suggested next action
- Auditor decisions (Confirmed / Not Substantiated / Request Evidence / Refer / False Positive)
  with mandatory rationale
- Append-only audit log
- Working-paper PDF report separating machine analysis from human-approved findings
- Configurable rule parameters (VAT/WHT rates) — rates are parameters, not legal truth

## Run
```
pip install -r requirements.txt
streamlit run app.py
```
