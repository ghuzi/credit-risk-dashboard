import io
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

LABELS = [
    ("age", "Age"),
    ("monthly_income", "Monthly income (PKR)"),
    ("card_limit", "Total credit limit (PKR)"),
    ("card_balance", "Amount owed on cards and credit lines (PKR)"),
    ("monthly_debt", "Monthly loan instalments (PKR)"),
    ("late_30_59", "Times 30-59 days late"),
    ("late_60_89", "Times 60-89 days late"),
    ("late_90", "Times 90+ days late"),
    ("open_lines", "Open loans and credit lines"),
    ("real_estate", "Real estate loans"),
    ("dependents", "Number of dependents"),
]
DISPLAY_ONLY = [
    ("yearly_revenue", "Yearly revenue (PKR)"),
    ("tax_paid", "Tax paid last year (PKR)"),
    ("repayment_record", "Repayment record"),
]


def _fmt(v):
    if isinstance(v, float):
        return f"{v:,.0f}" if v == int(v) else f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def _table(rows):
    t = Table(rows, colWidths=[9.5 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F3F5")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def make_pdf(rec):
    # Build a one-borrower PDF report from a saved record; returns bytes
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    s = getSampleStyleSheet()
    res, vals, ratios = rec["result"], rec["values"], rec["ratios"]
    story = [
        Paragraph("Credit Risk Report", s["Title"]),
        Paragraph(f"Report ID: {rec['id']} &nbsp;|&nbsp; Saved: {rec['saved_at']} &nbsp;|&nbsp; File: {rec['file_name']}", s["Normal"]),
        Spacer(1, 0.5 * cm),
        Paragraph("Result", s["Heading2"]),
        _table([
            ["Item", "Value"],
            ["Default probability (calibrated)", f"{res['default_probability'] * 100:.1f}%"],
            ["Risk band", res["risk_band"]],
            ["Flag for review (15% cut-off)", "Yes" if res["flag_for_review"] else "No"],
            ["Credit usage ratio", f"{ratios.get('credit_usage', 0):.2f}"],
            ["Debt ratio (instalments / income)", f"{ratios.get('debt_ratio', 0):.2f}"],
            ["Monthly income sent to model (USD)", f"{res['income_usd_used']:,.0f}"],
        ]),
        Spacer(1, 0.4 * cm),
        Paragraph("Answers used by the model", s["Heading2"]),
        _table([["Question", "Answer"]] + [[lab, _fmt(vals[k])] for k, lab in LABELS if k in vals]),
        Spacer(1, 0.4 * cm),
        Paragraph("Shown for information only (not used by the model)", s["Heading2"]),
        _table([["Question", "Answer"]] + [[lab, _fmt(vals[k])] for k, lab in DISPLAY_ONLY if k in vals]),
    ]
    if rec.get("warnings"):
        story += [Spacer(1, 0.3 * cm), Paragraph("Warnings", s["Heading2"])]
        story += [Paragraph("- " + w, s["Normal"]) for w in rec["warnings"]]
    story += [
        Spacer(1, 0.5 * cm),
        Paragraph("Limits", s["Heading2"]),
        Paragraph(
            "This estimate comes from a model trained on a 2011 public US-style consumer-credit dataset, "
            "not on Pakistani borrowers. Income was converted from PKR to USD at a fixed approximate rate. "
            "The debt ratio uses loan instalments only, which approximates the ratio in the training data. "
            "Revenue, tax and repayment record do not affect the probability. "
            "This is not a validated default probability and must not be used alone for lending decisions.",
            s["Normal"]),
    ]
    doc.build(story)
    return buf.getvalue()


def records_to_df(records):
    rows = []
    for r in records:
        row = {
            "report_id": r["id"], "saved_at": r["saved_at"], "file_name": r["file_name"],
            "default_probability_pct": round(r["result"]["default_probability"] * 100, 2),
            "risk_band": r["result"]["risk_band"],
            "flag_for_review": r["result"]["flag_for_review"],
        }
        row.update(r["values"])
        rows.append(row)
    return pd.DataFrame(rows)


def make_csv(records):
    return records_to_df(records).to_csv(index=False).encode("utf-8")