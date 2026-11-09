"""Part A task 6 -- run the seven queries in sql/queries.sql against data/instamart.db."""
import re
import sqlite3

import pandas as pd

from config import DB_PATH, SQL_PATH, Report


def load_queries(path=SQL_PATH):
    """Split queries.sql on its '-- Qn' marker lines -> {"Q1": sql, ...}."""
    text = open(path, encoding="utf-8").read()
    parts = re.split(r"^-- (Q\d+):.*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


rep = Report("a4_sql")
con = sqlite3.connect(DB_PATH)
res = {name: pd.read_sql_query(sql, con) for name, sql in load_queries().items()}
con.close()

q2, q5, q6, q7 = res["Q2"], res["Q5"], res["Q6"], res["Q7"]
top_q2 = q2.iloc[0]
tops = q6[q6["row_num"] == 1]
rank_ne_row = int((q6["rnk"] != q6["row_num"]).sum())

checks = [
    ("Q1", "customers with >INR 8000 in completed orders above INR 500", len(res["Q1"]), "30"),
    ("Q2", "rows / sum of revenue", f"{len(q2)} / INR {q2['revenue'].sum():,.2f}", "30 / INR 2,998,668.80"),
    ("Q2", "largest cell", f"{top_q2.city} / {top_q2.category} INR {top_q2.revenue:,.2f}",
     "Bengaluru / Electronics INR 233,909.45"),
    ("Q3", "products above average price", len(res["Q3"]), "11"),
    ("Q4", "customers without a completed order", len(res["Q4"]), "25"),
    ("Q5", "customers above average / average spend", f"{len(q5)} / INR {q5['avg_spend'].iloc[0]:,.2f}",
     "550 / INR 2,552.06"),
    ("Q6", "rows where RANK() != ROW_NUMBER()", rank_ne_row, "8"),
    ("Q7", "daily rows / last cumulative", f"{len(q7)} / INR {q7['cumulative_revenue'].iloc[-1]:,.2f}",
     "183 / INR 2,998,668.80"),
]
rep.table("SQL results vs reference", pd.DataFrame(checks, columns=["query", "result", "ours", "reference"]))
rep.table("Q6 -- top customer per city", tops[["city", "customer_id", "total_spend"]])
rep.table("Q6 -- rows where ties make RANK() differ from ROW_NUMBER()", q6[q6["rnk"] != q6["row_num"]])
rep.save()

assert len(res["Q1"]) == 30 and len(q2) == 30 and round(q2["revenue"].sum(), 2) == 2998668.80
assert (top_q2.city, top_q2.category, top_q2.revenue) == ("Bengaluru", "Electronics", 233909.45)
assert len(res["Q3"]) == 11 and len(res["Q4"]) == 25
assert len(q5) == 550 and q5["avg_spend"].iloc[0] == 2552.06
assert dict(zip(tops["city"], tops["customer_id"])) == {
    "Bengaluru": "C0082", "Chennai": "C0930", "Delhi": "C0291",
    "Hyderabad": "C0743", "Mumbai": "C0693", "Pune": "C0426"}
assert rank_ne_row == 8
assert len(q7) == 183 and q7["cumulative_revenue"].iloc[-1] == 2998668.80
