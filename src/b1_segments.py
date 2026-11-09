"""Part B tasks 1-3 -- RFM table, K-means model selection, segment profiles, PCA, customer_segments.csv."""
import os

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from config import CLEAN, OUTPUTS, SEED, SNAPSHOT, Report

FINAL_K = 4
rep = Report("b1_segments")

# ---------------- task 1: RFM ----------------
orders = pd.read_csv(os.path.join(CLEAN, "orders.csv"), parse_dates=["order_ts"])
comp = orders[orders["status"] == "completed"]
rfm = comp.groupby("customer_id").agg(last_ts=("order_ts", "max"),
                                      frequency=("order_id", "nunique"),
                                      monetary=("order_amount", "sum"))
rfm["recency"] = (pd.Timestamp(SNAPSHOT) - rfm["last_ts"]).dt.days
rfm = rfm[["recency", "frequency", "monetary"]].reset_index()
rfm["monetary"] = rfm["monetary"].round(2)

rfm_stats = pd.DataFrame([
    ("customers", len(rfm)),
    ("recency median / min / max (days)", f"{rfm.recency.median():g} / {rfm.recency.min()} / {rfm.recency.max()}"),
    ("frequency mean / max", f"{rfm.frequency.mean():.2f} / {rfm.frequency.max()}"),
    ("monetary mean / max (INR)", f"{rfm.monetary.mean():,.2f} / {rfm.monetary.max():,.2f}"),
], columns=["RFM statistic", "value"])
rep.table(f"RFM table as of {SNAPSHOT}", rfm_stats)

# ---------------- task 2: K-means for K = 2..8 ----------------
X = StandardScaler().fit_transform(rfm[["recency", "frequency", "monetary"]])
rows, models = [], {}
for k in range(2, 9):
    km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(X)
    models[k] = km
    rows.append((k, round(km.inertia_, 1), round(silhouette_score(X, km.labels_), 3)))
kt = pd.DataFrame(rows, columns=["K", "inertia", "silhouette"])
rep.table("K-means model selection (scaled RFM)", kt, floatfmt="{:.3f}")

# ---------------- task 3: profile, name, PCA ----------------
rfm["segment_id"] = models[FINAL_K].labels_
prof = (rfm.groupby("segment_id")
           .agg(size=("customer_id", "count"), mean_recency=("recency", "mean"),
                mean_frequency=("frequency", "mean"), mean_monetary=("monetary", "mean"))
           .round(2))

# Names are assigned from each cluster's profile, not from its id (cluster ids are arbitrary labels).
premium_id = prof["mean_monetary"].idxmax()
rest = prof.drop(premium_id)
lapsing_id = rest["mean_recency"].idxmax()
loyal_id = rest.drop(lapsing_id)["mean_frequency"].idxmax()
NAMES = {
    premium_id: ("Premium Big Spenders", "Protect with a VIP desk, early access to electronics launches and priority support"),
    loyal_id: ("Loyal Regulars", "Reward with a subscription / loyalty pass and basket-building bundles on staples"),
    lapsing_id: ("Lapsing Customers", "Win back with a time-boxed comeback coupon and a 'we miss you' push"),
}
for sid in prof.index:
    NAMES.setdefault(sid, ("Occasional Shoppers", "Nudge to a second weekly order with free-delivery thresholds and reminders"))
prof["segment_name"] = [NAMES[s][0] for s in prof.index]
prof["recommended_action"] = [NAMES[s][1] for s in prof.index]
prof["is_premium"] = prof.index == premium_id
rep.table(f"Segment profiles for K={FINAL_K} (segment ids are arbitrary labels with no ordering)",
          prof.reset_index())

pca = PCA(n_components=2, random_state=SEED).fit(X)
evr = pca.explained_variance_ratio_
rep.add(f"PCA explained_variance_ratio_: {evr[0]:.3f}, {evr[1]:.3f} (total {evr.sum():.3f})\n")
rep.save()

rfm["segment_name"] = rfm["segment_id"].map(prof["segment_name"])
rfm["is_premium"] = rfm["segment_id"] == premium_id
rfm[["customer_id", "recency", "frequency", "monetary", "segment_id", "segment_name", "is_premium"]].to_csv(
    os.path.join(OUTPUTS, "customer_segments.csv"), index=False)
print("wrote outputs/customer_segments.csv")

assert len(rfm) == 1175 and rfm.recency.median() == 19 and rfm.recency.max() == 180
assert round(rfm.frequency.mean(), 2) == 9.46 and rfm.frequency.max() == 33
assert round(rfm.monetary.mean(), 2) == 2552.06 and rfm.monetary.max() == 14766.55
assert all(abs(a - b) <= 0.05 * b for a, b in zip(sorted(prof["size"]), sorted([436, 138, 419, 182])))
assert prof.loc[premium_id, "size"] == prof["size"].min() and abs(prof.loc[premium_id, "mean_monetary"] - 7130) < 100
assert abs(evr[0] - 0.634) <= 0.02 and abs(evr[1] - 0.218) <= 0.02
