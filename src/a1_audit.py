"""Part A task 2 -- audit the raw exports (shape, dtypes, missing values, planted defects)."""
import os

import pandas as pd

from config import RAW, Report

rep = Report("a1_audit")
customers = pd.read_csv(os.path.join(RAW, "customers.csv"))
products = pd.read_csv(os.path.join(RAW, "products.csv"))
# keep literal "N/A" as text: only truly blank cells are missing, so unparseable amounts are counted
orders = pd.read_csv(os.path.join(RAW, "orders.csv"), keep_default_na=False, na_values=[""])

rep.add("### Raw table profiles\n")
for name, df in [("customers.csv", customers), ("products.csv", products), ("orders.csv", orders)]:
    prof = pd.DataFrame({
        "column": df.columns,
        "dtype": [str(t) for t in df.dtypes],
        "missing": df.isna().sum().values,
        "missing_pct": (df.isna().mean() * 100).round(2).values,
    })
    rep.table(f"{name} -- shape {df.shape[0]:,} rows x {df.shape[1]} columns", prof)

amount_num = pd.to_numeric(orders["order_amount"], errors="coerce")
delivery = pd.to_numeric(orders["delivery_minutes"], errors="coerce")
age = pd.to_numeric(customers["age"], errors="coerce")
gender = customers["gender"].dropna()

audit = [
    ("raw orders.csv rows", len(orders), 13084),
    ("exact duplicate rows", int(orders.duplicated().sum()), 119),
    ("rows with status pending", int((orders["status"] == "pending").sum()), 656),
    ("distinct order_id", orders["order_id"].nunique(), 12309),
    ("non-numeric order_amount", int((amount_num.isna() & orders["order_amount"].notna()).sum()), 120),
    ("negative delivery_minutes", int((delivery < 0).sum()), 106),
    ("blank delivery_minutes", int(orders["delivery_minutes"].isna().sum()), 2541),
    ("blank age", int(age.isna().sum()), 61),
    ("age outside 10-100", int(((age < 10) | (age > 100)).sum()), 6),
    ("distinct raw city spellings", customers["city"].nunique(), 24),
    ("distinct non-blank raw gender spellings", gender.nunique(), 10),
    ("blank gender", int(customers["gender"].isna().sum()), 30),
]
audit_df = pd.DataFrame(audit, columns=["check", "value", "reference"])
audit_df["match"] = (audit_df["value"] == audit_df["reference"]).map({True: "yes", False: "NO"})
rep.table("Audit figures", audit_df)
rep.save()
assert (audit_df["match"] == "yes").all(), "audit mismatch"
