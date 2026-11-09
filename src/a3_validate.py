"""Part A task 5 -- assert reference checkpoints on the stored clean data."""
import os
import sqlite3

import pandas as pd

from config import CLEAN, DB_PATH

cust = pd.read_csv(os.path.join(CLEAN, "customers.csv"))
orders = pd.read_csv(os.path.join(CLEAN, "orders.csv"))
comp = orders[orders["status"] == "completed"]
canc = orders[orders["status"] == "cancelled"]

assert cust["city"].value_counts().to_dict() == {
    "Pune": 227, "Delhi": 210, "Bengaluru": 197, "Chennai": 191, "Hyderabad": 191, "Mumbai": 184}
assert cust["gender"].value_counts().to_dict() == {"female": 610, "male": 560, "unknown": 30}
assert cust["age"].isna().sum() == 0 and cust["age"].between(18, 60).all()
assert len(orders) == 12309 and orders["order_id"].is_unique
assert len(comp) == 11110 and len(canc) == 1199
assert not (orders["status"] == "pending").any()
assert orders["order_amount"].isna().sum() == 0
assert comp["delivery_minutes"].isna().sum() == 0 and canc["delivery_minutes"].isna().sum() == 1199
assert round(comp["order_amount"].sum(), 2) == 2998668.80
assert (orders["delivery_minutes"].dropna() >= 0).all()

with sqlite3.connect(DB_PATH) as con:
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"customers", "products", "orders"} <= tables
    assert con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 12309
    ts = con.execute("SELECT order_ts FROM orders LIMIT 1").fetchone()[0]
    assert len(ts) == 19 and ts[10] == " ", ts   # stored as text YYYY-MM-DD HH:MM:SS

print("ALL CHECKPOINTS PASSED")
