import numpy as np
import pandas as pd

# Fixed, adjustable conversion rate (placeholder; set to the rate you want to use)
PKR_PER_USD = 278.0


def build_features(values, ratios, feature_order, pkr_per_usd=PKR_PER_USD):
    # Map parser output to the ten model inputs (income converted to USD)
    row = {
        "RevolvingUtilizationOfUnsecuredLines": ratios["credit_usage"],
        "age": values["age"],
        "NumberOfTime30-59DaysPastDueNotWorse": values["late_30_59"],
        "DebtRatio": ratios["debt_ratio"],
        "MonthlyIncome": values["monthly_income"] / pkr_per_usd,
        "NumberOfOpenCreditLinesAndLoans": values["open_lines"],
        "NumberOfTimes90DaysLate": values["late_90"],
        "NumberRealEstateLoansOrLines": values["real_estate"],
        "NumberOfTime60-89DaysPastDueNotWorse": values["late_60_89"],
        "NumberOfDependents": values["dependents"],
    }
    return pd.DataFrame([row])[feature_order]


def score_values(bundle, values, ratios, pkr_per_usd=PKR_PER_USD):
    # Raw score -> sigmoid calibration -> probability -> band -> flag
    X = build_features(values, ratios, bundle["feature_order"], pkr_per_usd)
    raw = float(bundle["pipeline"].predict_proba(X)[:, 1][0])
    p = min(max(raw, 1e-6), 1 - 1e-6)
    prob = float(bundle["calibrator"].predict_proba(np.array([[np.log(p / (1 - p))]]))[:, 1][0])
    band = pd.cut([prob], bins=bundle["band_edges"], labels=bundle["band_labels"],
                  include_lowest=True, right=False)[0]
    return {
        "raw_score": raw,
        "default_probability": prob,
        "risk_band": str(band),
        "flag_for_review": bool(prob >= bundle["flag_cutoff"]),
        "income_usd_used": float(X["MonthlyIncome"].iloc[0]),
    }


def score_form(bundle, parsed, pkr_per_usd=PKR_PER_USD):
    # Refuse to predict if the form has any error
    if not parsed["ok"]:
        raise ValueError("Form has errors; no prediction made: " + "; ".join(parsed["errors"]))
    return score_values(bundle, parsed["values"], parsed["ratios"], pkr_per_usd)
FRIENDLY = {
    "RevolvingUtilizationOfUnsecuredLines": "Credit card usage",
    "age": "Age",
    "NumberOfTime30-59DaysPastDueNotWorse": "Times 30-59 days late",
    "DebtRatio": "Debt ratio",
    "MonthlyIncome": "Monthly income",
    "NumberOfOpenCreditLinesAndLoans": "Open loans and credit lines",
    "NumberOfTimes90DaysLate": "Times 90+ days late",
    "NumberRealEstateLoansOrLines": "Real estate loans",
    "NumberOfTime60-89DaysPastDueNotWorse": "Times 60-89 days late",
    "NumberOfDependents": "Number of dependents",
}

_explainer_cache = {}


def explain_values(bundle, values, ratios, pkr_per_usd=PKR_PER_USD, top_n=5):
    # Top reasons for one borrower from SHAP on the raw score (ranking and direction only)
    import shap
    pipe = bundle["pipeline"]
    rf = pipe.steps[-1][1]
    prep = pipe[:-1]
    X = build_features(values, ratios, bundle["feature_order"], pkr_per_usd)
    Xt = prep.transform(X)
    if not isinstance(Xt, pd.DataFrame):
        Xt = pd.DataFrame(Xt, columns=prep.get_feature_names_out())
    if "e" not in _explainer_cache:
        _explainer_cache["e"] = shap.TreeExplainer(rf)
    sv = _explainer_cache["e"].shap_values(Xt)
    if isinstance(sv, list):
        sv = sv[1]
    elif getattr(sv, "ndim", 2) == 3:
        sv = sv[:, :, 1]
    contrib = pd.Series(np.asarray(sv)[0], index=Xt.columns)
    out = []
    for col, val in contrib.items():
        base = col.split("__")[-1]
        if base.startswith("missingindicator_"):
            name = "Monthly income not reported (flag)"
        else:
            name = FRIENDLY.get(base, base)
        out.append((name, float(val)))
    out.sort(key=lambda t: abs(t[1]), reverse=True)
    return out[:top_n]
