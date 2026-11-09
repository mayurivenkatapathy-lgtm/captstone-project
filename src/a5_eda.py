"""Part A task 7 -- pandas cross-check of Q2 and exploratory statistics of completed order_amount."""
import os
import sqlite3

import pandas as pd

from a4_sql import load_queries
from config import CLEAN, DB_PATH, Report, md_table

rep = Report("a5_eda")
orders = pd.read_csv(os.path.join(CLEAN, "orders.csv"))
cust = pd.read_csv(os.path.join(CLEAN, "customers.csv"))
products = pd.read_csv(os.path.join(CLEAN, "products.csv"))
comp = (orders[orders["status"] == "completed"]
        .merge(cust[["customer_id", "city"]], on="customer_id")
        .merge(products[["product_id", "category"]], on="product_id"))

# (a) Q2 rebuilt with pivot_table, grand total vs SQL
pivot = pd.pivot_table(comp, values="order_amount", index="city", columns="category",
                       aggfunc="sum", margins=True, margins_name="Total").round(2)
with sqlite3.connect(DB_PATH) as con:
    sql_total = round(pd.read_sql_query(load_queries()["Q2"], con)["revenue"].sum(), 2)
grand = round(pivot.loc["Total", "Total"], 2)
rep.table("Q2 rebuilt with pd.pivot_table(margins=True) (INR)", pivot.reset_index())
rep.add(f"Pivot grand total INR {grand:,.2f} = SQL Q2 total INR {sql_total:,.2f}: {grand == sql_total}\n")

by_city = (comp.groupby("city")
               .agg(sum_inr=("order_amount", "sum"), mean_inr=("order_amount", "mean"),
                    count=("order_amount", "count"))
               .round(2).reset_index())
rep.table("Completed order_amount per city (groupby + named aggregation)", by_city)

# (b) distribution of completed order_amount
amt = comp["order_amount"]
q1, q3 = amt.quantile(0.25), amt.quantile(0.75)
iqr = q3 - q1
lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
stats = pd.DataFrame([
    ("mean", amt.mean()), ("median", amt.median()), ("skewness", amt.skew()),
    ("Q1", q1), ("Q3", q3), ("IQR", iqr), ("lower fence", lo), ("upper fence", hi),
    ("outliers below lower fence", float((amt < lo).sum())),
    ("outliers above upper fence", float((amt > hi).sum())),
], columns=["statistic", "value"])
rep.table("Completed order_amount distribution (INR)", stats)

corr = comp[["order_amount", "discount_pct", "quantity", "delivery_minutes"]].corr().round(3)
rep.table("Correlation matrix (completed orders)", corr.reset_index(), floatfmt="{:.3f}")
pairs = corr.where(~pd.DataFrame([[i >= j for j in range(4)] for i in range(4)],
                                  index=corr.index, columns=corr.columns)).stack()
top_pair = pairs.abs().idxmax()
rep.add(f"Largest |correlation|: {top_pair[0]} vs {top_pair[1]} = {pairs[top_pair]:.3f}\n")
rep.save()

bl, mu = by_city.set_index("city").loc["Bengaluru"], by_city.set_index("city").loc["Mumbai"]
assert grand == sql_total == 2998668.80
assert (bl.sum_inr, bl.mean_inr, bl["count"]) == (523643.40, 276.47, 1894)
assert (mu.sum_inr, mu.mean_inr, mu["count"]) == (479058.50, 297.00, 1613)
assert round(amt.mean(), 2) == 269.91 and amt.median() == 135.0 and abs(amt.skew() - 4.61) < 0.01
assert round(hi, 2) == 645.30 and (amt > hi).sum() == 897 and (amt < lo).sum() == 0
assert set(top_pair) == {"order_amount", "discount_pct"}
