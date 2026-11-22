import os
import hashlib
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import joblib
import form_parser
import scoring
import history
import reports

st.set_page_config(page_title="Credit Risk Dashboard", layout="wide")

GREEN, PINK, PURPLE = "#3ECF6E", "#F08CF0", "#A78BFA"
HERE = os.path.dirname(os.path.abspath(__file__))


@st.cache_resource
def load_bundle():
    return joblib.load(os.path.join(HERE, "model", "credit_risk_bundle.joblib"))


# ---------- Styling ----------
st.markdown("""
<style>
.stApp {background-color:#F4F5F7;}
.stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp li, .stApp span, .stApp label {color:#111111;}
[data-testid="stSidebar"] {background-color:#111214;}
[data-testid="stSidebar"] * {color:#E8E8E8 !important;}
[data-testid="stHeader"] {background:transparent;}
.block-container {padding-top:3.5rem;}
[data-testid="stAlert"], [data-testid="stAlert"] * {color:#FFFFFF !important;}
[data-testid="stDownloadButton"] button, [data-testid="stDownloadButton"] button * {color:#FFFFFF !important;}
[data-testid="stFileUploader"] section, [data-testid="stFileUploader"] section * {color:#FFFFFF !important;}
.kpi {background:#FFFFFF;border-radius:12px;padding:14px 16px;min-height:150px;border:1px solid #E6E8EB;}
.kpi .label {font-size:13px;color:#6B7280;}
.kpi .value {font-size:22px;font-weight:600;color:#111111;margin:4px 0;}
.kpi .note {font-size:12px;color:#6B7280;}
.tag-demo {background:#FEF3C7;color:#92400E !important;padding:2px 8px;border-radius:6px;font-size:12px;}
.tag-real {background:#DCFCE7;color:#166534 !important;padding:2px 8px;border-radius:6px;font-size:12px;}
</style>
""", unsafe_allow_html=True)

DEMO_TAG = '<span class="tag-demo">DEMO DATA</span>'
REAL_TAG = '<span class="tag-real">REAL RESULTS</span>'


def kpi(col, label, value, note):
    col.markdown(
        f'<div class="kpi"><div class="label">{label}</div>'
        f'<div class="value">{value}</div><div class="note">{note}</div></div>',
        unsafe_allow_html=True,
    )


def style(fig, height=300):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10), height=height,
        font=dict(color="#111111"), legend=dict(orientation="h", y=1.12),
    )
    fig.update_xaxes(automargin=True, tickfont=dict(color="#111111"))
    fig.update_yaxes(automargin=True, gridcolor="#ECEEF1", tickfont=dict(color="#111111"))
    return fig


def reasons_chart(rec):
    # Top 5 reasons for one saved report (SHAP on the raw score)
    rs = scoring.explain_values(load_bundle(), rec["values"], rec["ratios"])
    names = [n for n, _ in rs][::-1]
    vals = [v for _, v in rs][::-1]
    cols = [PINK if v > 0 else GREEN for v in vals]
    fig = go.Figure(go.Bar(x=vals, y=names, orientation="h", marker_color=cols))
    fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=True)
    return fig


# ---------- Sidebar ----------
st.sidebar.markdown("## CREDIT RISK")
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Upload form", "Models", "Explainability", "Reports"],
    label_visibility="collapsed",
)
st.sidebar.caption("Trained on a 2011 public consumer-credit dataset. Not validated for real lending decisions.")


# ======================= Upload form =======================
if page == "Upload form":
    st.title("Upload form")
    st.markdown("Upload the filled borrower Word form (.docx). The form is checked first; no estimate is made if it has errors.")

    tpl = os.path.join(HERE, "templates", "borrower_form.docx")
    if os.path.exists(tpl):
        with open(tpl, "rb") as f:
            st.download_button("Download blank form", f.read(), file_name="borrower_form.docx")

    up = st.file_uploader("Filled form (.docx)", type=["docx"])
    if up is not None:
        try:
            parsed = form_parser.parse_form(up)
        except Exception:
            st.error("Could not read this file. Please upload the .docx form downloaded above.")
            st.stop()

        if not parsed["ok"]:
            st.error("The form has problems. Please fix them and upload again:")
            for e in parsed["errors"]:
                st.write("- " + e)
        else:
            for w in parsed["warnings"]:
                st.warning(w)
            res = scoring.score_form(load_bundle(), parsed)

            fhash = hashlib.sha256(up.getvalue()).hexdigest()[:16]
            existing = next((r for r in history.load_records() if r["file_hash"] == fhash), None)
            if existing:
                rec = existing
                st.info("Form accepted. This exact file was already saved earlier, so it was not saved again.")
            else:
                rec = history.save_record(up.name, fhash, parsed, res)
                st.success("Form accepted and the report was saved.")
            st.session_state["current_id"] = rec["id"]

            c = st.columns(3)
            kpi(c[0], "Default probability", f"{res['default_probability']*100:.1f}%", "calibrated estimate")
            kpi(c[1], "Risk band", res["risk_band"].split(" (")[0], res["risk_band"])
            kpi(c[2], "Flag for review", "Yes" if res["flag_for_review"] else "No", "15% cut-off")
            st.caption(
                f"Monthly income was converted at {scoring.PKR_PER_USD:g} PKR per USD "
                f"(about {res['income_usd_used']:,.0f} USD) because the model was trained on a US-style dataset. "
                "This is an approximation, not a validated default probability for Pakistani borrowers."
            )
    st.stop()


# ======================= Reports =======================
if page == "Reports":
    st.title("Reports")
    recs = history.load_records()
    if not recs:
        st.info("No saved reports yet. Upload a valid form first.")
        st.stop()

    df_rep = reports.records_to_df(recs).iloc[::-1]
    st.markdown(f"**{len(recs)} saved report(s)**, newest first.")
    st.dataframe(
        df_rep[["report_id", "saved_at", "file_name", "default_probability_pct", "risk_band", "flag_for_review"]],
        hide_index=True, use_container_width=True,
    )
    st.download_button("Download all reports (CSV)", reports.make_csv(recs),
                       file_name="credit_risk_reports.csv", mime="text/csv")

    st.markdown("**Download one report as PDF**")
    options = {f"{r['saved_at']} | {r['file_name']} | {r['result']['default_probability']*100:.1f}%": r
               for r in reversed(recs)}
    choice = st.selectbox("Choose a report", list(options.keys()))
    chosen = options[choice]
    st.download_button("Download report (PDF)", reports.make_pdf(chosen),
                       file_name=f"credit_risk_report_{chosen['id']}.pdf", mime="application/pdf")
    st.stop()


# ======================= Explainability =======================
if page == "Explainability":
    st.title("Explainability")
    st.markdown("**What the model relies on most (all borrowers)**")
    st.markdown(REAL_TAG + " Average importance on the raw risk score, not percentages.", unsafe_allow_html=True)
    img = os.path.join(HERE, "model", "shap_importance.png")
    if os.path.exists(img):
        st.image(img, width=650)
    else:
        st.warning("Importance chart image not found in the model folder.")
    st.write(
        "Credit card usage and past late payments matter most. Age, number of open loans, income "
        "and debt ratio matter less. Number of dependents and the 'income not reported' flag barely matter."
    )

    st.markdown("---")
    st.markdown("**Reasons for one borrower**")
    recs = history.load_records()
    if not recs:
        st.info("No saved reports yet. Upload a valid form to see reasons for a borrower.")
    else:
        opts = {f"{r['saved_at']} | {r['file_name']} | {r['result']['default_probability']*100:.1f}%": r
                for r in reversed(recs)}
        choice = st.selectbox("Report", list(opts.keys()), key="expl_report")
        try:
            with st.container(border=True):
                st.plotly_chart(style(reasons_chart(opts[choice])), use_container_width=True, theme=None)
            st.caption("Pink bars push the risk up, green bars push it down. "
                       "Bar length shows ranking on the model's raw score, not percentages.")
        except Exception:
            st.info("Reasons could not be computed for this report.")

    st.caption("This shows what the model used, not what truly causes default. "
               "The model was trained on a 2011 US-style dataset, and age is a model input that is often restricted in real lending.")
    st.stop()


# ======================= Models =======================
if page == "Models":
    st.title("Models")
    st.markdown("**Model comparison (5-fold cross-validation on training data)**")
    st.markdown(REAL_TAG + " Class weights balanced for all three models.", unsafe_allow_html=True)
    cmp_df = pd.DataFrame({
        "Model": ["Random Forest", "Decision Tree", "Logistic Regression"],
        "PR-AUC": [0.388, 0.352, 0.350],
        "ROC-AUC": [0.864, 0.849, 0.856],
        "Recall": ["0.747", "n/a", "n/a"],
        "Precision": ["0.225", "n/a", "n/a"],
        "F1": ["0.346", "n/a", "n/a"],
    })
    st.dataframe(cmp_df, hide_index=True, use_container_width=True)
    st.caption("Random guessing would score a PR-AUC of about 0.066. The Random Forest lead is real but modest.")

    st.markdown("---")
    st.markdown("**Final model**")
    with st.container(border=True):
        st.write("Tuned Random Forest: 250 trees, minimum 40 samples per leaf, half of the inputs tried at each split, "
                 "maximum depth 10, balanced subsample class weights.")
        st.write("Because class weights inflate raw scores, a sigmoid (Platt) calibrator turns them into realistic "
                 "probabilities. Only the calibrated probability is shown to users.")
        st.write("Risk bands: Low under 5%, Medium 5-15%, High 15-30%, Very high 30% and above. "
                 "Review flag at 15%.")

    st.markdown("**Honest notes**")
    st.markdown(
        "- Tuning gave no meaningful gain: the top four settings were within 0.002 PR-AUC of each other.\n"
        "- Logistic Regression and Decision Tree were not tuned, so the comparison favours the tuned model slightly.\n"
        "- The test set was used once, after all choices were fixed.\n"
        "- Removed rows: 609 duplicates, 1 age issue and 225 rows with special late-payment codes (96/98).\n"
        "- Trained on a 2011 US-style dataset, not Pakistani borrowers. Not validated for real lending decisions."
    )
    st.stop()


# ======================= Dashboard =======================
st.title("Dashboard")

recs = history.load_records()
is_demo = len(recs) == 0
sfx = " (demo)" if is_demo else ""
r = None

if is_demo:
    st.markdown(DEMO_TAG + " No saved reports yet, so made-up example values are shown.", unsafe_allow_html=True)
    b = {"prob": 0.124, "band": "Medium (5-15%)", "flag": "No", "income": 85000,
         "revenue": 1200000, "tax": 96000, "age": 39, "late": [1, 0, 0], "record": "On time"}
else:
    opts = {f"{x['saved_at']} | {x['file_name']} | {x['result']['default_probability']*100:.1f}%": x
            for x in reversed(recs)}
    keys = list(opts.keys())
    cur = st.session_state.get("current_id")
    idx = next((i for i, k in enumerate(keys) if opts[k]["id"] == cur), 0)
    choice = st.selectbox("Report", keys, index=idx)
    r = opts[choice]
    v, res = r["values"], r["result"]
    st.markdown(REAL_TAG + f" Report {r['id']}, saved {r['saved_at']}.", unsafe_allow_html=True)
    b = {"prob": res["default_probability"], "band": res["risk_band"],
         "flag": "Yes" if res["flag_for_review"] else "No",
         "income": v["monthly_income"], "revenue": v["yearly_revenue"], "tax": v["tax_paid"],
         "age": v["age"], "late": [v["late_30_59"], v["late_60_89"], v["late_90"]],
         "record": v["repayment_record"]}

c = st.columns(6)
kpi(c[0], "Default probability", f"{b['prob']*100:.1f}%", "calibrated" + sfx)
kpi(c[1], "Risk band", b["band"].split(" (")[0], "range: " + b["band"].split(" (")[1].rstrip(")") + sfx)
kpi(c[2], "Flag for review", b["flag"], "15% cut-off" + sfx)
kpi(c[3], "Monthly income (PKR)", f"{b['income']:,.0f}", "used by the model (as USD)")
kpi(c[4], "Yearly revenue (PKR)", f"{b['revenue']:,.0f}", "display only")
kpi(c[5], "Tax paid (PKR)", f"{b['tax']:,.0f}", "display only")

st.write("")
tab1, tab2, tab3, tab4 = st.tabs(["Snapshot", "Why this score", "Financial details", "Model performance"])

# ---------- Tab 1: Snapshot ----------
with tab1:
    left, right = st.columns([2, 1])
    with left:
        with st.container(border=True):
            st.markdown("**Late payments in the last 2 years**")
            st.markdown(DEMO_TAG if is_demo else REAL_TAG, unsafe_allow_html=True)
            labels = ["30-59 days late", "60-89 days late", "90+ days late"]
            fig = go.Figure()
            fig.add_bar(x=labels, y=b["late"], name="This borrower", marker_color=GREEN)
            if is_demo:
                fig.add_bar(x=labels, y=[0.3, 0.1, 0.1], name="Average borrower", marker_color=PINK)
            fig.update_layout(barmode="group")
            st.plotly_chart(style(fig), use_container_width=True, theme=None)
            if not is_demo:
                st.caption("The comparison with the average borrower is not shown yet; it needs real training-data averages.")
    with right:
        with st.container(border=True):
            st.markdown("**Top reasons for this score**")
            if is_demo:
                st.markdown(DEMO_TAG, unsafe_allow_html=True)
                reasons = {"Credit card usage": 0.9, "30-59 days late": 0.6, "Age": 0.3, "Open loans": 0.2}
                fig = go.Figure(go.Bar(
                    x=list(reasons.values())[::-1], y=list(reasons.keys())[::-1],
                    orientation="h", marker_color=GREEN,
                ))
                fig.update_xaxes(showticklabels=False, showgrid=False)
                st.plotly_chart(style(fig), use_container_width=True, theme=None)
            else:
                st.markdown(REAL_TAG, unsafe_allow_html=True)
                try:
                    st.plotly_chart(style(reasons_chart(r)), use_container_width=True, theme=None)
                    st.caption("Pink bars push the risk up, green bars push it down. "
                               "Bar length shows ranking on the model's raw score, not percentages.")
                except Exception:
                    st.info("Reasons could not be computed for this report.")

# ---------- Tab 2: Why this score ----------
with tab2:
    st.markdown("**What the model relies on most (all borrowers, from training sample)**")
    st.markdown(REAL_TAG + " Average importance on the raw risk score, not percentages.", unsafe_allow_html=True)
    img = os.path.join(HERE, "model", "shap_importance.png")
    if os.path.exists(img):
        st.image(img, width=650)
    else:
        st.warning("Importance chart image not found in the model folder.")
    st.caption("This shows what the model used, not what truly causes default.")

# ---------- Tab 3: Financial details ----------
with tab3:
    details = pd.DataFrame({
        "Detail": ["Age", "Monthly income (PKR)", "Yearly revenue (PKR)", "Tax paid (PKR)", "Repayment record"],
        "Value": [str(b["age"]), f"{b['income']:,.0f}", f"{b['revenue']:,.0f}", f"{b['tax']:,.0f}", b["record"]],
        "Used by the model?": ["Yes", "Yes (converted to USD)", "No (display only)", "No (display only)", "No (display only)"],
    })
    with st.container(border=True):
        st.markdown(DEMO_TAG if is_demo else REAL_TAG, unsafe_allow_html=True)
        st.dataframe(details, hide_index=True, use_container_width=True)
    st.caption("Revenue, tax and repayment record are not in the training data, so they cannot change the probability.")

# ---------- Tab 4: Model performance ----------
with tab4:
    st.markdown(REAL_TAG + " Final exam on 29,833 borrowers the model had never seen.", unsafe_allow_html=True)
    m = st.columns(6)
    kpi(m[0], "PR-AUC", "0.386", "random guessing: 0.066")
    kpi(m[1], "ROC-AUC", "0.855", "95% range 0.847-0.865")
    kpi(m[2], "Brier score", "0.0495", "lazy baseline: 0.0618")
    kpi(m[3], "Flagged", "11.3%", "at 15% cut-off")
    kpi(m[4], "Recall", "0.561", "defaulters caught")
    kpi(m[5], "Precision", "0.329", "flagged who default")
    st.write("")
    with st.container(border=True):
        st.markdown("**Predicted vs real default rate by risk band (test set, %)**")
        bands = ["Low (under 5%)", "Medium (5-15%)", "High (15-30%)", "Very high (30%+)"]
        fig = go.Figure()
        fig.add_bar(x=bands, y=[1.7, 8.7, 21.4, 46.4], name="Predicted", marker_color=GREEN)
        fig.add_bar(x=bands, y=[1.7, 8.8, 21.4, 44.5], name="Real", marker_color=PINK)
        fig.update_layout(barmode="group")
        st.plotly_chart(style(fig), use_container_width=True, theme=None)
    st.caption("Trained on a 2011 consumer-credit dataset, not Pakistani borrowers. Age is a model input but is often restricted in real lending.")