import math
from docx import Document

# kind: "int" = whole number, "num" = any number
# lo/hi = allowed range; lo_strict = value must be strictly above lo
FIELDS = {
    "age":            dict(kind="int", lo=18, hi=100),
    "monthly_income": dict(kind="num", lo=0, lo_strict=True),
    "card_limit":     dict(kind="num", lo=0, lo_strict=True),
    "card_balance":   dict(kind="num", lo=0),
    "monthly_debt":   dict(kind="num", lo=0),
    "late_30_59":     dict(kind="int", lo=0, hi=98),
    "late_60_89":     dict(kind="int", lo=0, hi=98),
    "late_90":        dict(kind="int", lo=0, hi=98),
    "open_lines":     dict(kind="int", lo=0, hi=100),
    "real_estate":    dict(kind="int", lo=0, hi=100),
    "dependents":     dict(kind="int", lo=0, hi=20),
    "yearly_revenue": dict(kind="num", lo=0),
    "tax_paid":       dict(kind="num", lo=0),
}
RECORD_CHOICES = {"on time": "On time", "sometimes late": "Sometimes late", "often late": "Often late"}


def read_form(path):
    # Return {field_id: answer_text} from every table row of the form
    doc = Document(path)
    raw = {}
    for table in doc.tables:
        for row in table.rows[1:]:
            cells = row.cells
            if len(cells) >= 3:
                raw[cells[0].text.strip()] = cells[2].text.strip()
    return raw


def _to_number(text):
    t = text.replace(",", "").replace(" ", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def validate_form(raw):
    errors, warnings, values = [], [], {}

    for fid, rule in FIELDS.items():
        if fid not in raw:
            errors.append(f"{fid}: field is missing from the form (wrong template?)")
            continue
        text = raw[fid].strip()
        if text == "":
            errors.append(f"{fid}: answer is blank (write 0 if the answer is none)")
            continue
        v = _to_number(text)
        if v is None:
            errors.append(f"{fid}: '{text}' is not a number")
            continue
        if rule["kind"] == "int":
            if not float(v).is_integer():
                errors.append(f"{fid}: must be a whole number, got '{text}'")
                continue
            v = int(v)
        lo, hi = rule.get("lo"), rule.get("hi")
        if lo is not None:
            if rule.get("lo_strict") and v <= lo:
                errors.append(f"{fid}: must be greater than {lo}, got {text}")
                continue
            if not rule.get("lo_strict") and v < lo:
                errors.append(f"{fid}: must be at least {lo}, got {text}")
                continue
        if hi is not None and v > hi:
            errors.append(f"{fid}: must be at most {hi}, got {text}")
            continue
        values[fid] = v

    # Repayment record (display only)
    rec = raw.get("repayment_record", "").strip().lower()
    if rec == "":
        errors.append("repayment_record: answer is blank")
    elif rec not in RECORD_CHOICES:
        errors.append("repayment_record: write On time, Sometimes late or Often late")
    else:
        values["repayment_record"] = RECORD_CHOICES[rec]

    # Cross-field checks
    if "real_estate" in values and "open_lines" in values and values["real_estate"] > values["open_lines"]:
        errors.append("real_estate: cannot be more than the total number of open loans and credit lines")

    # Ratios (only when their inputs are valid)
    ratios = {}
    if "card_balance" in values and "card_limit" in values:
        ratios["credit_usage"] = values["card_balance"] / values["card_limit"]
        if ratios["credit_usage"] > 1:
            warnings.append("card_balance is above card_limit (over the limit); allowed, but check it")
    if "monthly_debt" in values and "monthly_income" in values:
        ratios["debt_ratio"] = values["monthly_debt"] / values["monthly_income"]
    if "tax_paid" in values and "yearly_revenue" in values and values["tax_paid"] > values["yearly_revenue"]:
        warnings.append("tax_paid is above yearly_revenue; check it (display only)")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings,
            "values": values, "ratios": ratios}


def parse_form(path):
    return validate_form(read_form(path))
