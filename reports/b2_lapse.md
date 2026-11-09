**Lapse cohort (cutoff 2025-09-01; label = no completed order 2025-09-01..2025-09-30)**

| item | value |
|---|---|
| cohort customers | 1156 |
| lapsed | 443 (38.32%) |
| train / test rows | 924 / 232 |
| baseline 'never lapsed' test accuracy | 61.6% |
| baseline lapsed-class F1 | 0.00 |

Scaler mean of frequency learned on train rows: 8.1147 vs full-cohort mean 8.0285 -- they differ because the scaler only saw the 924 training rows.

Missing values in any feature column: 0

**Grid search (cv=5, scoring=f1, train rows only)**

| model | best params | best CV F1 |
|---|---|---|
| LogisticRegression | {'C': 100} | 0.651 |
| RandomForest | {'max_depth': 8, 'min_samples_leaf': 10} | 0.681 |

**Test-set results, lapsed = positive class**

| model | TN | FP | FN | TP | precision | recall | f1 |
|---|---|---|---|---|---|---|---|
| Baseline (always not lapsed) | 143 | 0 | 89 | 0 | 0.000 | 0.000 | 0.000 |
| LogisticRegression (tuned) | 111 | 32 | 31 | 58 | 0.644 | 0.652 | 0.648 |
| RandomForest (tuned) | 113 | 30 | 31 | 58 | 0.659 | 0.652 | 0.655 |

Selected model: **RandomForest** (higher cross-validated F1); test F1 0.655

Balanced training set: {1: 570, 0: 570} (added 216 duplicate lapsed rows)

**Class-balance experiment (same untouched test set)**

| model | TN | FP | FN | TP | precision | recall | f1 |
|---|---|---|---|---|---|---|---|
| LogisticRegression (original train) | 111 | 32 | 31 | 58 | 0.644 | 0.652 | 0.648 |
| LogisticRegression (oversampled train) | 90 | 53 | 13 | 76 | 0.589 | 0.854 | 0.697 |

**Random forest -- top 5 feature importances**

| feature | importance |
|---|---|
| frequency | 0.280 |
| monetary | 0.271 |
| recency | 0.115 |
| avg_delivery_minutes | 0.061 |
| cancel_rate | 0.052 |

**Logistic regression -- coefficient signs (standardised features)**

| feature | coefficient |
|---|---|
| recency | 0.040 |
| frequency | -1.698 |
| cancel_rate | -0.124 |

Reloaded outputs/lapse_model.joblib reproduces all 232 test predictions exactly: True

**Retention list -- Premium customers in the test set (40 total), top 10 by lapse probability**

| customer_id | lapse_probability | actually_lapsed |
|---|---|---|
| C0862 | 0.4910 | 0 |
| C1112 | 0.4841 | 0 |
| C0060 | 0.4798 | 0 |
| C0802 | 0.4796 | 0 |
| C1008 | 0.4778 | 0 |
| C1000 | 0.4624 | 0 |
| C0525 | 0.4597 | 1 |
| C0133 | 0.4562 | 0 |
| C0267 | 0.4525 | 0 |
| C0565 | 0.4499 | 1 |

Truly lapsed among the listed customers: 2 of 10

