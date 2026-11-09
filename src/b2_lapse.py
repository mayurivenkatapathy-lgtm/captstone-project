"""Part B tasks 4-8 -- lapse cohort, leakage-free pipeline, tuned models, oversampling, persistence, retention list."""
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import CLEAN, CUTOFF, OUTPUTS, SEED, Report

rep = Report("b2_lapse")
cutoff = pd.Timestamp(CUTOFF)
sept_end = pd.Timestamp("2025-10-01")

orders = pd.read_csv(os.path.join(CLEAN, "orders.csv"), parse_dates=["order_ts"])
products = pd.read_csv(os.path.join(CLEAN, "products.csv"))
cust = pd.read_csv(os.path.join(CLEAN, "customers.csv"), parse_dates=["signup_date"])
orders = orders.merge(products[["product_id", "category"]], on="product_id")

# ---------------- task 4: cohort, label and features (only orders before the cutoff) ----------------
hist = orders[orders["order_ts"] < cutoff]                       # the ONLY order rows features may see
hist_comp = hist[hist["status"] == "completed"]
cohort = np.sort(hist_comp["customer_id"].unique())

sept_buyers = set(orders.loc[(orders["status"] == "completed") & (orders["order_ts"] >= cutoff)
                             & (orders["order_ts"] < sept_end), "customer_id"])

g = hist_comp.groupby("customer_id")
feat = pd.DataFrame({
    "recency": (cutoff - g["order_ts"].max()).dt.days,
    "frequency": g["order_id"].nunique(),
    "monetary": g["order_amount"].sum(),
    "avg_discount_pct": g["discount_pct"].mean(),
    "avg_delivery_minutes": g["delivery_minutes"].mean(),
})
status_counts = hist.groupby("customer_id")["status"].value_counts().unstack(fill_value=0)
feat["cancel_rate"] = status_counts["cancelled"] / (status_counts["cancelled"] + status_counts["completed"])
cat_counts = hist_comp.groupby(["customer_id", "category"]).size().rename("n").reset_index()
feat["fav_category"] = (cat_counts.sort_values(["customer_id", "n", "category"], ascending=[True, False, True])
                                  .drop_duplicates("customer_id").set_index("customer_id")["category"])
feat = feat.loc[cohort].join(cust.set_index("customer_id")[["city", "age", "gender", "signup_date"]])
feat["tenure_days"] = (cutoff - feat["signup_date"]).dt.days
feat = feat.drop(columns="signup_date")
y = pd.Series([int(c not in sept_buyers) for c in feat.index], index=feat.index, name="lapsed")

NUM = ["recency", "frequency", "monetary", "avg_discount_pct", "cancel_rate", "avg_delivery_minutes", "age", "tenure_days"]
CAT = ["city", "gender", "fav_category"]
X = feat[NUM + CAT]

# leakage guards
assert hist["order_ts"].max() < cutoff
assert not any("segment" in c for c in X.columns)
assert X.isna().sum().sum() == 0, "missing values in features"

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
base_pred = np.zeros(len(y_te), dtype=int)
cohort_tbl = pd.DataFrame([
    ("cohort customers", len(X)),
    ("lapsed", f"{y.sum()} ({y.mean():.2%})"),
    ("train / test rows", f"{len(X_tr)} / {len(X_te)}"),
    ("baseline 'never lapsed' test accuracy", f"{accuracy_score(y_te, base_pred):.1%}"),
    ("baseline lapsed-class F1", f"{f1_score(y_te, base_pred, zero_division=0):.2f}"),
], columns=["item", "value"])
rep.table(f"Lapse cohort (cutoff {CUTOFF}; label = no completed order 2025-09-01..2025-09-30)", cohort_tbl)

# ---------------- task 5: preprocessing fitted on training rows only ----------------
def make_pipe(clf):
    pre = ColumnTransformer([("num", StandardScaler(), NUM),
                             ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), CAT)])
    return Pipeline([("pre", pre), ("clf", clf)])

probe = make_pipe(LogisticRegression(max_iter=1000)).fit(X_tr, y_tr)
scaler_mean = probe.named_steps["pre"].named_transformers_["num"].mean_[NUM.index("frequency")]
rep.add(f"Scaler mean of frequency learned on train rows: {scaler_mean:.4f} vs full-cohort mean "
        f"{X['frequency'].mean():.4f} -- they differ because the scaler only saw the 924 training rows.\n")
rep.add(f"Missing values in any feature column: {int(X.isna().sum().sum())}\n")

# ---------------- task 6: tune and evaluate ----------------
lr_gs = GridSearchCV(make_pipe(LogisticRegression(max_iter=1000)),
                     {"clf__C": [0.01, 0.1, 1, 10, 100]}, cv=5, scoring="f1").fit(X_tr, y_tr)
rf_gs = GridSearchCV(make_pipe(RandomForestClassifier(n_estimators=100, random_state=SEED)),
                     {"clf__max_depth": [3, 5, 8], "clf__min_samples_leaf": [5, 10, 20]},
                     cv=5, scoring="f1").fit(X_tr, y_tr)


def metrics(name, model, Xt=X_te, yt=y_te):
    p = model.predict(Xt)
    tn, fp, fn, tp = confusion_matrix(yt, p).ravel()
    return {"model": name, "TN": tn, "FP": fp, "FN": fn, "TP": tp,
            "precision": round(precision_score(yt, p, zero_division=0), 3),
            "recall": round(recall_score(yt, p, zero_division=0), 3),
            "f1": round(f1_score(yt, p, zero_division=0), 3)}


tune = pd.DataFrame([
    ("LogisticRegression", str({k.replace("clf__", ""): v for k, v in lr_gs.best_params_.items()}), round(lr_gs.best_score_, 3)),
    ("RandomForest", str({k.replace("clf__", ""): v for k, v in rf_gs.best_params_.items()}), round(rf_gs.best_score_, 3)),
], columns=["model", "best params", "best CV F1"])
rep.table("Grid search (cv=5, scoring=f1, train rows only)", tune, floatfmt="{:.3f}")
test_tbl = pd.DataFrame([
    {"model": "Baseline (always not lapsed)", "TN": int((y_te == 0).sum()), "FP": 0, "FN": int(y_te.sum()), "TP": 0,
     "precision": 0.0, "recall": 0.0, "f1": 0.0},
    metrics("LogisticRegression (tuned)", lr_gs.best_estimator_),
    metrics("RandomForest (tuned)", rf_gs.best_estimator_)])
rep.table("Test-set results, lapsed = positive class", test_tbl, floatfmt="{:.3f}")

# model selection uses cross-validated F1 only, so the test set never drives a choice
best_name, best = (("RandomForest", rf_gs.best_estimator_) if rf_gs.best_score_ >= lr_gs.best_score_
                   else ("LogisticRegression", lr_gs.best_estimator_))
best_f1 = f1_score(y_te, best.predict(X_te))
rep.add(f"Selected model: **{best_name}** (higher cross-validated F1); test F1 {best_f1:.3f}\n")

# ---------------- task 7: oversample the minority class in the training set only ----------------
train = X_tr.assign(lapsed=y_tr)
need = int((train["lapsed"] == 0).sum() - (train["lapsed"] == 1).sum())
extra = train[train["lapsed"] == 1].sample(n=need, replace=True, random_state=SEED)
balanced = pd.concat([train, extra])
lr_bal = clone(lr_gs.best_estimator_).fit(balanced[NUM + CAT], balanced["lapsed"])
bal_tbl = pd.DataFrame([metrics("LogisticRegression (original train)", lr_gs.best_estimator_),
                        metrics("LogisticRegression (oversampled train)", lr_bal)])
rep.add(f"Balanced training set: {balanced['lapsed'].value_counts().to_dict()} (added {need} duplicate lapsed rows)\n")
rep.table("Class-balance experiment (same untouched test set)", bal_tbl, floatfmt="{:.3f}")

# ---------------- task 8: interpret, persist, use ----------------
rf_model = rf_gs.best_estimator_
names = [n.split("__", 1)[1] for n in rf_model.named_steps["pre"].get_feature_names_out()]
imp = (pd.DataFrame({"feature": names, "importance": rf_model.named_steps["clf"].feature_importances_})
         .sort_values("importance", ascending=False).head(5).round(3))
rep.table("Random forest -- top 5 feature importances", imp, floatfmt="{:.3f}")
lr_model = lr_gs.best_estimator_
coef = pd.DataFrame({"feature": names, "coefficient": lr_model.named_steps["clf"].coef_[0]})
coef = coef.set_index("feature").loc[["recency", "frequency", "cancel_rate"]].round(3).reset_index()
rep.table("Logistic regression -- coefficient signs (standardised features)", coef, floatfmt="{:.3f}")

model_path = os.path.join(OUTPUTS, "lapse_model.joblib")
joblib.dump(best, model_path)
reloaded = joblib.load(model_path)
same = bool((reloaded.predict(X_te) == best.predict(X_te)).all())
rep.add(f"Reloaded outputs/lapse_model.joblib reproduces all {len(X_te)} test predictions exactly: {same}\n")

seg = pd.read_csv(os.path.join(OUTPUTS, "customer_segments.csv")).set_index("customer_id")
test_ids = X_te.index[X_te.index.isin(seg.index[seg["is_premium"]])]
ret = pd.DataFrame({"customer_id": test_ids,
                    "lapse_probability": best.predict_proba(X_te.loc[test_ids])[:, 1].round(4),
                    "actually_lapsed": y_te.loc[test_ids].values})
ret = ret.sort_values(["lapse_probability", "customer_id"], ascending=[False, True]).head(10)
ret.to_csv(os.path.join(OUTPUTS, "retention_list.csv"), index=False)
rep.table(f"Retention list -- Premium customers in the test set ({len(test_ids)} total), top 10 by lapse probability",
          ret, floatfmt="{:.4f}")
rep.add(f"Truly lapsed among the listed customers: {int(ret['actually_lapsed'].sum())} of {len(ret)}\n")
rep.save()

assert len(X) == 1156 and y.sum() == 443 and len(X_tr) == 924 and len(X_te) == 232
assert round(accuracy_score(y_te, base_pred), 3) == 0.616
assert balanced["lapsed"].value_counts().tolist() == [570, 570]
assert best_f1 >= 0.55 and same
