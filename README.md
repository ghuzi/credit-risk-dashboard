# Credit Risk Dashboard

Upload a filled borrower Word form (.docx). The app validates it, estimates a calibrated default probability, assigns a risk band, flags it for review, and explains the top reasons.

## What it does
- Reads and validates a DOCX form (clear errors for bad input)
- Calibrated Random Forest estimate of default probability
- Risk bands: Low (<5%), Medium (5-15%), High (15-30%), Very high (30%+); review flag at 15%
- Top-5 reasons per borrower (SHAP, ranking only, not percentages)
- PDF and CSV reports

## Model results (held-out test set)
PR-AUC 0.386, ROC-AUC 0.855, Brier 0.0495 (baseline 0.0618), recall 0.561, precision 0.329, 11.3% flagged.

## Limits (please read)
- Trained on the 2011 "Give Me Some Credit" US dataset, not Pakistani borrowers. Not validated for real lending decisions.
- Monthly income is converted from PKR to USD at a fixed approximate rate.
- Yearly revenue, tax paid and repayment record are display only; they do not affect the probability.
- Tuning gave no real improvement over the baseline settings.
- Report history is per browser session and is lost on refresh.
- Age is a model input but is often restricted in real lending.

## Run locally
    pip install -r requirements.txt
    streamlit run app.py

Use made-up data only on the public demo.