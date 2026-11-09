"""Part A tasks 3-5 -- clean customers and orders, write data/clean/*.csv and data/instamart.db."""
import os
import sqlite3

import pandas as pd

from config import CLEAN, DB_PATH, RAW, Report, md_table

rep = Report("a2_clean")
rules = []   # (table, rule, rows/values changed)

# ---------------- customers ----------------
cust = pd.read_csv(os.path.join(RAW, "customers.csv"))

before = cust["city"].copy()
cust["city"] = cust["city"].str.strip().str.title()
rules.append(("customers", "city: strip spaces + title case", int((before != cust["city"]).sum())))

GENDER = {"male": "male", "m": "male", "female": "female", "f": "female"}
before = cust["gender"].copy()
cust["gender"] = cust["gender"].str.strip().str.lower().map(GENDER).fillna("unknown")
rules.append(("customers", "gender: map spellings to male/female, blank -> unknown",
              int((before.fillna("") != cust["gender"]).sum())))

cust["age"] = pd.to_numeric(cust["age"], errors="coerce")
bad_age = (cust["age"] < 10) | (cust["age"] > 100)
rules.append(("customers", "age: outside 10-100 -> missing", int(bad_age.sum())))
cust.loc[bad_age, "age"] = pd.NA
n_missing_age = int(cust["age"].isna().sum())
cust["age"] = cust["age"].fillna(cust.groupby("city")["age"].transform("median"))
rules.append(("customers", "age: fill missing with city median (groupby + transform)", n_missing_age))

cust["signup_date"] = pd.to_datetime(cust["signup_date"], format="%Y-%m-%d")
rules.append(("customers", "signup_date: parse to datetime", len(cust)))

# ---------------- products (already clean) ----------------
products = pd.read_csv(os.path.join(RAW, "products.csv"))

# ---------------- orders ----------------
orders = pd.read_csv(os.path.join(RAW, "orders.csv"), keep_default_na=False, na_values=[""])
orders["order_ts"] = pd.to_datetime(orders["order_ts"], format="%Y-%m-%d %H:%M:%S")
rules.append(("orders", "1. order_ts: parse to datetime", len(orders)))

n = len(orders)
orders = orders.drop_duplicates()
rules.append(("orders", "2. drop exact duplicate rows", n - len(orders)))

n = len(orders)
orders = (orders.sort_values(["order_id", "order_ts"])
                .drop_duplicates("order_id", keep="last")
                .reset_index(drop=True))
rules.append(("orders", "3. keep latest order_ts per order_id (drops earlier pending records)", n - len(orders)))

orders["order_amount"] = pd.to_numeric(orders["order_amount"], errors="coerce")
missing_amt = orders["order_amount"].isna()
price = orders["product_id"].map(products.set_index("product_id")["price_inr"])
orders.loc[missing_amt, "order_amount"] = (
    price * orders["quantity"] * (1 - orders["discount_pct"] / 100)).round(2)[missing_amt]
rules.append(("orders", "4. order_amount: unparseable -> recomputed from price x qty x (1 - discount)",
              int(missing_amt.sum())))

orders["delivery_minutes"] = pd.to_numeric(orders["delivery_minutes"], errors="coerce")
neg = orders["delivery_minutes"] < 0
rules.append(("orders", "5a. delivery_minutes: negative -> missing", int(neg.sum())))
orders.loc[neg, "delivery_minutes"] = pd.NA

orders["category"] = orders["product_id"].map(products.set_index("product_id")["category"])
completed = orders["status"] == "completed"
cat_median = orders["delivery_minutes"].where(completed).groupby(orders["category"]).transform("median")
fill = completed & orders["delivery_minutes"].isna()
orders.loc[fill, "delivery_minutes"] = cat_median[fill]
rules.append(("orders", "5b. delivery_minutes: completed + missing -> category median of completed orders",
              int(fill.sum())))
rules.append(("orders", "5c. delivery_minutes: cancelled orders left missing (never delivered)",
              int((orders["status"] == "cancelled").sum())))
orders = orders.drop(columns="category").sort_values("order_id").reset_index(drop=True)

rep.table("Cleaning rules and rows/values changed",
          pd.DataFrame(rules, columns=["table", "rule", "changed"]))

# ---------------- after-cleaning summary ----------------
comp = orders[orders["status"] == "completed"]
canc = orders[orders["status"] == "cancelled"]
summary = [
    ("cities", ", ".join(f"{k} {v}" for k, v in cust["city"].value_counts().items())),
    ("genders", ", ".join(f"{k} {v}" for k, v in cust["gender"].value_counts().items())),
    ("missing ages / age range", f"{int(cust['age'].isna().sum())} / {cust['age'].min():g}-{cust['age'].max():g}"),
    ("order rows / distinct order_id", f"{len(orders):,} / {orders['order_id'].nunique():,}"),
    ("status counts", ", ".join(f"{k} {v:,}" for k, v in orders["status"].value_counts().items())),
    ("missing order_amount", int(orders["order_amount"].isna().sum())),
    ("missing delivery_minutes (completed / cancelled)",
     f"{int(comp['delivery_minutes'].isna().sum())} / {int(canc['delivery_minutes'].isna().sum()):,}"),
    ("sum of completed order_amount", f"INR {comp['order_amount'].sum():,.2f}"),
]
rep.add("**After cleaning**\n\n" + md_table(pd.DataFrame(summary, columns=["item", "value"])) + "\n")
rep.save()

# ---------------- store ----------------
cust_out = cust.assign(signup_date=cust["signup_date"].dt.strftime("%Y-%m-%d"))
orders_out = orders.assign(order_ts=orders["order_ts"].dt.strftime("%Y-%m-%d %H:%M:%S"))
cust_out.to_csv(os.path.join(CLEAN, "customers.csv"), index=False)
products.to_csv(os.path.join(CLEAN, "products.csv"), index=False)
orders_out.to_csv(os.path.join(CLEAN, "orders.csv"), index=False)

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
with sqlite3.connect(DB_PATH) as con:
    cust_out.to_sql("customers", con, index=False)
    products.to_sql("products", con, index=False)
    orders_out.to_sql("orders", con, index=False)
print(f"wrote data/clean/*.csv and {os.path.relpath(DB_PATH)}")
