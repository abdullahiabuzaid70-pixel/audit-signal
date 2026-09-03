"""
AuditSignal — Report generator.
Working-paper / findings PDF built from approved decisions.
Machine analysis vs human-approved findings are clearly separated.
"""
from datetime import datetime
from fpdf import FPDF

DISCLAIMER = ("This system provides analytical assistance. Final tax, legal and "
              "enforcement decisions remain with authorized professionals.")


def _ascii(text):
    """Make dynamic text safe for core PDF fonts (latin-1)."""
    return (str(text)
            .replace("\u2014", "-").replace("\u2013", "-")
            .replace("\u2018", "'").replace("\u2019", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u20a6", "NGN ")
            .encode("latin-1", "replace").decode("latin-1"))


class ReportPDF(FPDF):
    def header(self):
        self.set_font("helvetica", "B", 9)
        self.set_text_color(120)
        self.cell(0, 5, "AuditSignal - Working Paper / Findings Report (Prototype)", align="R")
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(130)
        self.multi_cell(0, 4, DISCLAIMER, align="C")
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")


def generate_report(case_meta, signals, decisions, audit_log):
    pdf = ReportPDF(format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Case info
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, "Audit Case Report", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(60)
    for label, val in [
        ("Case number", case_meta["case_number"]),
        ("Taxpayer", f"{case_meta['taxpayer_name']} - {case_meta['taxpayer_id']} (fictional)"),
        ("Audit period", f"{case_meta['period_start']} to {case_meta['period_end']}"),
        ("Report generated", datetime.now().strftime("%Y-%m-%d %H:%M")),
    ]:
        pdf.cell(45, 6, f"{label}:")
        pdf.cell(0, 6, _ascii(val), ln=True)

    # Methodology
    pdf.ln(4)
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "Methodology", ln=True)
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(60)
    pdf.multi_cell(0, 5,
        "Records were ingested, normalized and analyzed with deterministic audit checks "
        "(duplicate invoices, VAT mismatch, WHT mismatch, unusual transactions, missing evidence, "
        "related-party concentration). Every risk signal was generated with a reason code, affected "
        "records and a transparent score. Risk signals are analytical exceptions, not findings of law. "
        "Human-approved findings are listed separately below.")

    # Machine-generated analysis
    pdf.ln(3)
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "Machine-Generated Risk Signals (requires review)", ln=True)
    pdf.set_font("helvetica", "", 8.5)
    pdf.set_text_color(60)
    for s in signals[:50]:
        pdf.set_font("helvetica", "B", 8.5)
        pdf.write(4.5, _ascii(f"[{s['severity'].upper()}] {s['category']} - {s['signal_id']}  "))
        pdf.set_font("helvetica", "", 8.5)
        pdf.write(4.5, _ascii(f"NGN {s['affected_amount']:,.0f} - {s['explanation'][:180]}"))
        pdf.ln(5)

    # Human-approved findings
    pdf.ln(3)
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "Human-Approved Decisions", ln=True)
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(60)
    if not decisions:
        pdf.multi_cell(0, 5, "No decisions recorded yet.")
    for d in decisions:
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(0, 5.5, _ascii(f"{d['decision']} - {d['signal_id']} ({d['timestamp']})"), ln=True)
        pdf.set_font("helvetica", "", 9)
        if d.get("rationale"):
            pdf.multi_cell(0, 5, _ascii(f"Rationale: {d['rationale']}"))
        pdf.ln(1.5)

    # Audit trail
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "Audit Trail Summary", ln=True)
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(60)
    for entry in audit_log[-30:]:
        pdf.cell(0, 5, _ascii(f"{entry['timestamp']}  {entry['action']}"), ln=True)

    return bytes(pdf.output())
