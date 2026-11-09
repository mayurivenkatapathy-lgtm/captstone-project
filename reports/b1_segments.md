**RFM table as of 2025-10-01 00:00:00**

| RFM statistic | value |
|---|---|
| customers | 1175 |
| recency median / min / max (days) | 19 / 0 / 180 |
| frequency mean / max | 9.46 / 33 |
| monetary mean / max (INR) | 2,552.06 / 14,766.55 |

**K-means model selection (scaled RFM)**

| K | inertia | silhouette |
|---|---|---|
| 2 | 1820.800 | 0.465 |
| 3 | 1268.200 | 0.445 |
| 4 | 743.100 | 0.526 |
| 5 | 617.400 | 0.480 |
| 6 | 503.200 | 0.482 |
| 7 | 408.500 | 0.416 |
| 8 | 366.500 | 0.412 |

**Segment profiles for K=4 (segment ids are arbitrary labels with no ordering)**

| segment_id | size | mean_recency | mean_frequency | mean_monetary | segment_name | recommended_action | is_premium |
|---|---|---|---|---|---|---|---|
| 0 | 436 | 28.86 | 3.77 | 1,057.62 | Occasional Shoppers | Nudge to a second weekly order with free-delivery thresholds and reminders | False |
| 1 | 138 | 24.12 | 6.77 | 7,129.70 | Premium Big Spenders | Protect with a VIP desk, early access to electronics launches and priority support | True |
| 2 | 419 | 8.77 | 19.40 | 3,410.02 | Loyal Regulars | Reward with a subscription / loyalty pass and basket-building bundles on staples | False |
| 3 | 182 | 109.04 | 2.20 | 685.99 | Lapsing Customers | Win back with a time-boxed comeback coupon and a 'we miss you' push | False |

PCA explained_variance_ratio_: 0.634, 0.218 (total 0.852)

