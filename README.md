# Instamart Customer Intelligence & Support Copilot

## Overview

An internal tool for the (fictional) Instamart Customer Experience team. It addresses three problems from the weekly leadership review: raw order exports nobody trusts, no early warning for customers about to stop ordering, and a support desk buried in free-text tickets. The Copilot is built in four connected Parts. Each Part consumes the previous Part's output:

| Part | What it does | Consumes | Produces |
|---|---|---|---|
| A — Data Foundation | Audits and cleans the raw exports, stores them in SQLite, answers business questions in SQL and pandas | `data/raw/*.csv` | `data/clean/*.csv`, `data/instamart.db`, `sql/queries.sql` |
| B — Segments & Lapse | Customer segments (recency, frequency, monetary value + K-means) and a lapse-prediction model | clean orders and customers | `outputs/customer_segments.csv`, `outputs/lapse_model.joblib`, `outputs/retention_list.csv` |
| C — Ticket Triage | Guardrailed, PII-redacted, retrying, validated, budgeted ticket classification and segment-aware routing | tickets + Part B segments | `outputs/triage_results.csv`, `outputs/triage_budget_demo.csv` |
| D — Policy RAG & Refund Agent | TF-IDF policy question answering and a tool-calling refund agent with safe stops and crash recovery | policies + Part A database | `outputs/agent_runs.jsonl`, `outputs/refund_ledger.jsonl`, `state/` |

All data is synthetic and fictional, produced by the supplied `generate_data.py`. Every language-model call goes through the supplied offline `mock_llm.py`: no API key, no network and no cost. Both supplied files are committed unmodified. All money is in Indian Rupees (INR). Libraries used: the Python standard library, pandas, numpy, scikit-learn and joblib only.

**Repository layout**

```
generate_data.py, mock_llm.py     supplied files (unmodified)
requirements.txt, .gitignore      pip freeze of the venv; ignores .env, .venv/, __pycache__/
src/config.py                     shared paths, seeds, dates and a Markdown report writer
src/a1_audit.py … a5_eda.py       Part A
src/b1_segments.py, b2_lapse.py   Part B
src/c_triage.py                   Part C
src/d1_rag.py, d2_agent.py        Part D
sql/queries.sql                   Q1–Q7
data/ outputs/ state/             generated data, graded outputs, agent checkpoints
reports/                          Markdown tables written by each script (source of the numbers below)
```

Every script asserts its reference checkpoints and stops with an error if any number drifts.

## Reproduce

Tested with Python 3.11 on macOS; the pinned versions in `requirements.txt` also install on Python 3.12–3.14 (Linux, Windows, macOS). Run from the repository root:

1. `python3 -m venv .venv`
2. `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
3. `pip install -r requirements.txt`
4. `python generate_data.py` (last line: `generated: customers=1200 products=40 orders_raw=13084 tickets=164`)
5. `python src/a1_audit.py`
6. `python src/a2_clean.py`
7. `python src/a3_validate.py` (prints `ALL CHECKPOINTS PASSED`)
8. `python src/a4_sql.py`
9. `python src/a5_eda.py`
10. `python src/b1_segments.py`
11. `python src/b2_lapse.py`
12. `python src/c_triage.py`
13. `python src/d1_rag.py`
14. `python src/d2_agent.py`

## Part A

### Audit of the raw exports

Raw files are read with `keep_default_na=False, na_values=[""]`, so only truly blank cells count as missing. This keeps the literal text `N/A` visible as an unparseable amount.

| table | shape | missing values per column (count / %) |
|---|---|---|
| customers.csv | 1,200 × 5 | customer_id 0, city 0, signup_date 0, **age 61 (5.08%)**, **gender 30 (2.50%)** |
| products.csv | 40 × 4 | none |
| orders.csv | 13,084 × 9 | all 0 except **delivery_minutes 2,541 (19.42%)** |

Data types: ids, city, gender, dates, status and order_amount are read as text. order_amount is text because it contains `N/A` and `error`. quantity, discount_pct and price_inr are integers. age and delivery_minutes are floats because they have blanks.

| audit figure | value |
|---|---|
| raw orders.csv rows | 13,084 |
| exact duplicate rows | 119 |
| rows with status pending | 656 |
| distinct order_id | 12,309 |
| order_amount values that are not numbers | 120 |
| negative delivery_minutes | 106 |
| blank delivery_minutes | 2,541 |
| blank age | 61 |
| age outside 10–100 | 6 |
| distinct raw city spellings | 24 |
| distinct non-blank raw gender spellings | 10 |
| blank gender | 30 |

### Cleaning rules (in execution order) and what each changed

| table | rule | rows / values changed |
|---|---|---|
| customers | city: strip leading/trailing spaces, title case → exactly 6 cities | 476 |
| customers | gender: male/Male/M/m/MALE → male, female/Female/F/f/FEMALE → female, blank → unknown | 950 |
| customers | age outside 10–100 → missing | 6 |
| customers | missing age → median age of the customer's city (`groupby("city").transform("median")`) | 67 |
| customers | signup_date → datetime | 1,200 |
| orders | 1. order_ts → datetime | 13,084 |
| orders | 2. drop exact duplicate rows | 119 |
| orders | 3. keep only the record with the latest order_ts per order_id (removes the earlier `pending` copies) | 656 |
| orders | 4. order_amount → numeric. Unparseable amounts are recomputed as `round(price_inr × quantity × (1 − discount_pct/100), 2)` | 112 (the other 8 bad amounts sat on rows already removed in steps 2–3) |
| orders | 5a. negative delivery_minutes → missing | 105 (1 sat on a removed row) |
| orders | 5b. completed orders with missing delivery_minutes → median delivery time of that product category among completed orders (`groupby` + `transform`) | 774 |
| orders | 5c. cancelled orders keep delivery_minutes missing. A cancelled order was never delivered, so imputing a time would invent data | 1,199 left missing |

**After cleaning:**
- **Cities:** Pune 227, Delhi 210, Bengaluru 197, Chennai 191, Hyderabad 191, Mumbai 184.
- **Genders:** female 610, male 560, unknown 30.
- **Ages:** 0 missing, all between 18 and 60.
- **Orders:** 12,309 rows, one per order_id. 11,110 completed, 1,199 cancelled, 0 pending.
- **Missing values:** 0 missing order_amount. delivery_minutes is missing for 0 completed and 1,199 cancelled orders.
- **Completed revenue:** INR 2,998,668.80.

### Store and validate

- **Clean CSVs:** `data/clean/{customers,products,orders}.csv`.
- **SQLite:** `data/instamart.db` with tables `customers`, `products` and `orders`. order_ts is stored as text `YYYY-MM-DD HH:MM:SS`.
- **Validation:** `src/a3_validate.py` asserts 13 checkpoints (cities, genders, ages, row and status counts, no pending rows, no missing amounts, delivery gaps, revenue, the three tables in the database, the timestamp format) and prints **ALL CHECKPOINTS PASSED**.

### SQL analysis (`sql/queries.sql`, run with `pd.read_sql_query`)

| query | technique | result |
|---|---|---|
| Q1 | WHERE then HAVING | **30** customers whose completed orders above INR 500 total more than INR 8,000 |
| Q2 | three-table join | **30** city × category rows. Revenue sums to **INR 2,998,668.80**. Largest cell: **Bengaluru / Electronics INR 233,909.45** |
| Q3 | scalar subquery | **11** products priced above the average catalogue price |
| Q4 | LEFT JOIN | **25** customers with no completed order |
| Q5 | two CTEs | **550** customers above the average customer spend of **INR 2,552.06** |
| Q6 | RANK / DENSE_RANK / ROW_NUMBER by city | top spenders: Bengaluru C0082 (12,856.20), Chennai C0930 (10,151.40), Delhi C0291 (13,742.60), Hyderabad C0743 (12,730.05), Mumbai C0693 (14,766.55), Pune C0426 (10,377.10). **8** rows have RANK() ≠ ROW_NUMBER() |
| Q7 | running total `SUM() OVER (ORDER BY day)` | **183** daily rows. Last cumulative value **INR 2,998,668.80** |

Q6 ties: when two customers in a city have exactly the same total spend, RANK() gives both the same rank and skips the next number, but ROW_NUMBER() always gives distinct consecutive numbers. From the first tie onward in that city the two columns therefore differ. Here this happens in Bengaluru (2 rows), Mumbai (2) and Pune (4); for example two Pune customers each spent INR 285.00.

### pandas cross-check and exploratory analysis

**(a) Q2 rebuilt in pandas.** `pd.pivot_table(..., margins=True)` gives a grand total of **INR 2,998,668.80**, identical to the SQL total.

Completed order_amount by city (`groupby` + named aggregation):

| city | sum (INR) | mean (INR) | count |
|---|---|---|---|
| Bengaluru | 523,643.40 | 276.47 | 1,894 |
| Chennai | 463,629.15 | 272.72 | 1,700 |
| Delhi | 502,829.80 | 243.62 | 2,064 |
| Hyderabad | 528,589.90 | 284.95 | 1,855 |
| Mumbai | 479,058.50 | 297.00 | 1,613 |
| Pune | 500,918.05 | 252.48 | 1,984 |

**(b) Distribution of completed order_amount (INR).**

| statistic | value |
|---|---|
| mean / median | 269.91 / 135.00 |
| skewness | 4.61 |
| Q1 / Q3 / IQR | 64.80 / 297.00 / 232.20 |
| lower / upper 1.5×IQR fence | −283.50 / 645.30 |
| outliers below / above | 0 / 897 |

Correlation matrix over completed orders:

| | order_amount | discount_pct | quantity | delivery_minutes |
|---|---|---|---|---|
| order_amount | 1.000 | −0.095 | 0.087 | −0.003 |
| discount_pct | −0.095 | 1.000 | −0.000 | −0.010 |
| quantity | 0.087 | −0.000 | 1.000 | −0.013 |
| delivery_minutes | −0.003 | −0.010 | −0.013 | 1.000 |

**Questions answered.**
- **What is the data about?** Six months (April to September 2025) of quick-commerce orders from 1,175 active customers in six cities, across groceries, dairy, snacks, personal care and electronics.
- **What do the distributions look like?** Order value is strongly right-skewed: the mean of INR 269.91 is double the median of INR 135.00, and skewness is 4.61. Most baskets are cheap staples, and a long tail comes from electronics.
- **Are there outliers or anomalies?** 897 orders lie above the INR 645.30 upper fence and none below. These are genuine high-value electronics purchases, not errors, so they are kept. The real anomalies (negative times, text amounts, duplicates) were fixed during cleaning.
- **What relationships exist?** All pairwise correlations are weak. The largest in absolute value is order_amount with discount_pct at −0.095: bigger discounts go with slightly smaller bills. Next is order_amount with quantity at +0.087. A correlation this small does not establish causation.

## Part B

### RFM table (snapshot 2025-10-01 00:00:00, completed orders only)

| statistic | value |
|---|---|
| customers with a completed order | 1,175 |
| recency median / min / max (days) | 19 / 0 / 180 |
| frequency mean / max | 9.46 / 33 |
| monetary mean / max (INR) | 2,552.06 / 14,766.55 |

### K-means model selection (StandardScaler on R, F, M; `n_init=10, random_state=42`)

| K | inertia | silhouette |
|---|---|---|
| 2 | 1820.8 | 0.465 |
| 3 | 1268.2 | 0.445 |
| 4 | 743.1 | **0.526** |
| 5 | 617.4 | 0.480 |
| 6 | 503.2 | 0.482 |
| 7 | 408.5 | 0.416 |
| 8 | 366.5 | 0.412 |

**Chosen K = 4.**
- **Elbow:** inertia drops by 525 from K=3 to K=4, then only by 126 from K=4 to K=5. The elbow is at K=4.
- **Silhouette:** K=4 has the best score (0.526).
- **Business fit:** four segments map onto four distinct campaigns: protect, reward, nudge, win back.

Inertia always falls as K rises, because more centroids can only bring every point closer to its nearest centre; K equal to the number of customers would give an inertia of 0. A lower inertia at K=8 than at K=2 therefore says nothing about whether the extra clusters are real or actionable. That is why we read the elbow, check silhouette and ask whether the business can use the segments.

### Segment profiles (K = 4)

Cluster numbers are only labels with no ordering; names come from each cluster's profile.

| segment_id | name | size | mean recency (days) | mean frequency | mean monetary (INR) | recommended action |
|---|---|---|---|---|---|---|
| 1 | **Premium Big Spenders** (is_premium) | 138 | 24.1 | 6.77 | 7,129.70 | VIP desk, early access to electronics launches, priority support |
| 2 | Loyal Regulars | 419 | 8.8 | 19.40 | 3,410.02 | Subscription / loyalty pass and bundles on staples |
| 0 | Occasional Shoppers | 436 | 28.9 | 3.77 | 1,057.62 | Free-delivery thresholds and reminders to build a weekly habit |
| 3 | Lapsing Customers | 182 | 109.0 | 2.20 | 685.99 | Time-boxed comeback coupon and a "we miss you" push |

**PCA (2 components on the scaled RFM matrix):** explained_variance_ratio_ = **0.634** and **0.218**, total **0.852**.

Written to `outputs/customer_segments.csv` (customer_id, recency, frequency, monetary, segment_id, segment_name, is_premium).

### Lapse problem (cutoff 2025-09-01)

- **Cohort:** every customer with a completed order before the cutoff.
- **Label:** lapsed = 1 if the customer has no completed order from 2025-09-01 to 2025-09-30.
- **Features (from orders before the cutoff only, plus the clean customer table):**
  - numeric: recency, frequency, monetary, avg_discount_pct, cancel_rate (cancelled ÷ cancelled + completed), avg_delivery_minutes, age, tenure_days
  - nominal: city, gender, fav_category (most frequent category; ties broken alphabetically)

| item | value |
|---|---|
| cohort customers | 1,156 |
| lapsed | 443 (38.32%) |
| train / test rows (`stratify=y, random_state=42`) | 924 / 232 |
| baseline "always not lapsed" on test | accuracy 61.6%, lapsed-class F1 0.00 |

**Leakage controls, enforced in code.**
- **No future orders:** no order dated on or after 2025-09-01 enters any feature. The script asserts the maximum order date used is before the cutoff.
- **No segment labels:** the Part B segment labels are not features, and the script asserts no segment column is present.
- **Training rows only:** no encoder, scaler or resampler ever saw test rows. A `ColumnTransformer` with `StandardScaler` on the numeric features and `OneHotEncoder(drop="first")` (k−1 columns per variable) on city, gender and fav_category sits inside a scikit-learn `Pipeline` and is fitted on the training rows only. Oversampling touches the training set only.
- **No missing values:** the code confirms no feature column has any.

The scaler's learned mean of frequency is **8.1147**, against a full-cohort mean of **8.0285**. They differ because the scaler was fitted only on the 924 training rows, never on the 232 test rows.

### Tuning and test evaluation (lapsed = positive class)

| model | grid | best params | best CV F1 |
|---|---|---|---|
| LogisticRegression(max_iter=1000) | C ∈ {0.01, 0.1, 1, 10, 100} | C = 100 | 0.651 |
| RandomForestClassifier(n_estimators=100, random_state=42) | max_depth ∈ {3, 5, 8} × min_samples_leaf ∈ {5, 10, 20} (45 fits) | max_depth = 8, min_samples_leaf = 10 | 0.681 |

| model (test set) | TN | FP | FN | TP | precision | recall | F1 |
|---|---|---|---|---|---|---|---|
| Baseline (always not lapsed) | 143 | 0 | 89 | 0 | 0.000 | 0.000 | 0.000 |
| LogisticRegression (C=100) | 111 | 32 | 31 | 58 | 0.644 | 0.652 | 0.648 |
| RandomForest (depth 8, leaf 10) | 113 | 30 | 31 | 58 | 0.659 | 0.652 | **0.655** |

**Selected model: the random forest.** It has the higher cross-validated F1 (0.681 vs 0.651); the test set was used only after tuning. On test it catches the same 58 of 89 lapsing customers as logistic regression, with two fewer loyal customers wrongly flagged (30 vs 32).

For retention, missing a lapsing customer (a false negative) is the more expensive error: their future spend, roughly INR 2,500 per half-year for an average customer, walks away. Wrongly targeting a loyal customer (a false positive) only costs a discount coupon. Both models still miss 31 lapsers, so for a campaign we would lower the decision threshold or use the balanced training below to trade some precision for recall.

Our logistic regression chose C=100 where the reference chose C=1. This is because of our feature set; both F1 values are of the stated order and far above the 0.55 bar.

### Class-balance experiment (oversample lapsed training rows with replacement, `random_state=42`)

The balanced training set has 570 / 570 rows: 216 duplicate lapsed rows were added. The best logistic regression was refitted on it and evaluated on the original, unchanged test set:

| logistic regression | TN | FP | FN | TP | precision | recall | F1 |
|---|---|---|---|---|---|---|---|
| original training set | 111 | 32 | 31 | 58 | 0.644 | 0.652 | 0.648 |
| oversampled training set | 90 | 53 | 13 | 76 | 0.589 | **0.854** | 0.697 |

**Recall moved most, from 0.652 to 0.854.** Precision fell slightly, from 0.644 to 0.589; it did not rise. For the retention team this means the campaign would reach 76 of 89 lapsing customers instead of 58. The cost is 21 more loyal customers receiving an offer they did not need, a good trade when a coupon is cheaper than a lost customer.

### Interpretation, persistence and retention list

| random forest top-5 features | importance | business reading |
|---|---|---|
| frequency | 0.280 | How often someone orders is the strongest signal of whether they keep ordering |
| monetary | 0.271 | Customers with more spend at stake behave differently from low spenders |
| recency | 0.115 | A long gap since the last order is an early warning |
| avg_delivery_minutes | 0.061 | Slow past deliveries carry some signal about leaving |
| cancel_rate | 0.052 | A history of cancellations carries some signal |

| logistic regression feature | coefficient (standardised) | business reading |
|---|---|---|
| frequency | −1.698 (negative) | Each extra standard deviation of order frequency strongly lowers lapse odds; habits retain |
| recency | +0.040 (positive) | Longer since the last order means slightly higher lapse odds once frequency is known |
| cancel_rate | −0.124 (negative) | Slightly lower lapse odds, probably because engaged customers place and cancel more orders; this is not causal |

- **Persistence:** the selected model was saved with `joblib.dump` to `outputs/lapse_model.joblib`. After `joblib.load` it reproduces all 232 test predictions exactly.
- **Retention list:** 40 test-set customers are in the Premium segment. The 10 with the highest predicted lapse probability (0.450 to 0.491) are in `outputs/retention_list.csv`; **2 of those 10 truly lapsed**.
- **Caveat:** the Premium flag comes from the whole-window RFM, which includes September, the month that defines the lapse label. It is therefore a post-hoc whole-window label, and this retention list is illustrative, not a leakage-free evaluation. The model's own features still use only orders before 2025-09-01.

## Part C

### Pipeline (per ticket, in file order)

1. Input guardrails.
2. PII redaction.
3. An assertion that no email, phone or order id remains in the prompt.
4. A token-budget check.
5. A model call with retries.
6. Output validation.
7. Routing.

The user message sent to the model is exactly the redacted ticket text.

### Input guardrails and redaction

- **Guardrails:** 4 tickets are empty or whitespace (`skipped_empty`). 4 tickets estimate to **734 tokens**, above MAX_INPUT_TOKENS = 400 (`flagged_long`). None of these 8 is ever sent to the model.
- **Redaction:** applied in order: email → `[EMAIL]`, phone `\b[6-9]\d{9}\b` → `[PHONE]`, `ORD-\d{6}` → `[ORDER_ID]`.

| PII type | substitutions (all 164 tickets) |
|---|---|
| email | 55 |
| phone | 91 |
| order id | 132 |
| **total** | **278** |
| left after re-applying all three patterns | **0** |

### Prompts

Both system prompts contain **CLASSIFY**, list the four allowed categories (billing, delivery, technical, fraud) and demand a JSON-only reply `{"category": "...", "reason": "..."}`.

- **Zero-shot:** 45 estimated tokens, no examples.
- **Few-shot:** 108 estimated tokens. It adds an `EXAMPLES:` line with three labelled examples: fraud, technical, billing.

### Resilience and validation (one full zero-shot run over the 156 eligible tickets)

**Retries.** `mock_llm.reset()` runs before every full run, and every call goes through `call_with_retry`:
- up to 3 retries per ticket
- wait before retry n is 0.05 × 2ⁿ × uniform(0.9, 1.15) seconds
- one log line per retry with the ticket id, retry number and wait

Result: **19 TransientLLMErrors, all recovered on retry number 0**, with waits between 0.0453 and 0.0562 s (inside the 0.045–0.0575 range). No ticket ended with a permanent error.

**Validation.**
- JSON with an allowed category → `classified_json`.
- Not JSON → `re.findall(r"[a-z]+", text.lower())`. Exactly one allowed category word → `classified_keyword`.
- Anything else, including valid JSON with a category outside the list such as `"shipping"` → `flagged_invalid_output`. These go to human review; the pipeline never guesses.

| status | tickets |
|---|---|
| classified_json | 135 |
| classified_keyword | 12 |
| flagged_invalid_output | 9 |
| skipped_empty | 4 |
| flagged_long | 4 |

### Zero-shot vs few-shot (full runs, no budget)

| prompt | classified | accuracy on classified | total tokens | tokens per classified ticket |
|---|---|---|---|---|
| zero-shot | 147 | **85.7%** (126 / 147) | 11,428 | 77.7 |
| few-shot | 147 | **100.0%** (147 / 147) | 21,256 | 144.6 |

Zero-shot confusion table (rows = true, columns = predicted):

| true \ predicted | billing | delivery | fraud | technical |
|---|---|---|---|---|
| billing | 38 | 0 | 0 | 0 |
| delivery | 0 | 36 | 0 | 0 |
| fraud | 11 | 0 | 23 | 0 |
| technical | 10 | 0 | 0 | 29 |

Every zero-shot error is a billing false positive: 11 fraud tickets and 10 technical tickets mention a charge or payment and were filed as billing.

The few-shot prompt costs 66.9 more tokens per classified ticket (144.6 vs 77.7, +86%), or 9,828 extra tokens per 147 tickets. In exchange it removes all 21 errors. Eleven of those were fraud reports that zero-shot would have sent to the billing queue instead of the security team. Because a misrouted fraud ticket breaks the 2-hour security SLA and risks real customer losses, the extra tokens are clearly worth paying for here. Zero-shot would only be acceptable for a low-risk stream with no fraud-like vocabulary.

### Token budget, routing and outputs

- **Budget demo:** a zero-shot run with **TOKEN_BUDGET = 6000** stops calling the model once 6,021 tokens are spent. **74 tickets end `budget_exhausted`** and are routed to human review. Written to `outputs/triage_budget_demo.csv`.
- **Final run:** few-shot, TOKEN_BUDGET = 100000, 21,256 tokens used, 164 rows. Written to `outputs/triage_results.csv`. Routing reads `outputs/customer_segments.csv`; a customer missing from it counts as not premium.

| route | priority | rule | tickets |
|---|---|---|---|
| human_review | NORMAL | skipped_empty, flagged_long, flagged_invalid_output or budget_exhausted | 17 |
| security_team | HIGH | category fraud | 34 |
| premium_desk | HIGH | non-fraud, customer is_premium | 11 |
| support_queue | NORMAL | everything else | 102 |

**What was rule-validated and what went to humans.**
- **Rule-validated (147):** 135 replies were schema-checked JSON with an allowed category. 12 were chatty replies accepted only because exactly one allowed category word appeared.
- **Sent to human review (17), never guessed:** the 4 empty tickets, the 4 overlong tickets and the 9 invalid model outputs.

## Part D

### Chunking and retrieval

The five policy files are split into 40-word chunks with a 10-word overlap: each chunk starts 30 words after the previous one, stopping once a chunk reaches the last word. Result: **15 chunks**: refund 4, delivery 3, escalation 3, payment 3, privacy 2.

`TfidfVectorizer()` is fitted on the chunk texts and queries are ranked by `cosine_similarity`. `retrieve(query, k=3)` returns `[{source, score, text}]`. For "refund policy late delivery" the top three chunks are all from **refund_policy.txt** (scores 0.272, 0.251, 0.245).

TF (term frequency) measures how often a word occurs in a chunk. IDF (inverse document frequency) down-weights words that occur in many chunks, so rare, distinctive words like "electronics" or "wallet" count more than common ones. A limitation for this task: TF-IDF only matches exact word forms. A customer asking "can I get my money back if the rider was slow?" shares almost no words with "refund … delivered in more than 45 minutes", so a correct passage can be missed when the phrasing differs.

`answer(question)` sends two messages:
- a **POLICY ASSISTANT** system message (answer only from the context, otherwise say it could not find the information)
- a user message of the form `CONTEXT:\n[<file>]\n<chunk>…\nQUESTION:\n<question>`

It returns the reply and the sources used.

### Evaluation (`data/raw/policy_eval.csv`, 14 questions)

| chunking | expected doc in top 3 (12 answerable) | answer contains expected fact | fallback "I could not find…" (2 unanswerable) |
|---|---|---|---|
| 40 words, overlap 10 | **12 / 12** | **12 / 12** | **2 / 2** |
| 40 words, overlap 0 | 12 / 12 | **10 / 12** | 2 / 2 |

With overlap 0, two questions break even though the right document is retrieved:
- **"How soon is money returned when a payment fails but is deducted?"** The sentence "…the amount is returned automatically | within 48 hours." is cut at a chunk boundary. The best-matching chunk ends at "automatically", so the answer lacks "48 hours".
- **"What delivery time makes a completed order eligible for a full refund?"** "If a completed order is delivered in | more than 45 minutes…" is split, so the answer loses "more than 45 minutes".

The 10-word overlap keeps such sentences whole in at least one chunk.

### Tools

Each tool has a name, a one-sentence description and a JSON-style parameter spec in `TOOLS_SPEC`; `TOOL_MAP` maps names to functions.

| tool | what it does |
|---|---|
| `get_order(order_id)` | Reads `data/instamart.db` and returns order_id, status, order_amount, delivery_minutes, or `{"error": "order not found"}` |
| `search_policy(query)` | Returns `{"results": retrieve(query)}`, the same retrieval as above |
| `calculate_refund(order_amount, delivery_minutes)` | Full order_amount if delivered in more than 45 minutes, otherwise 0 |
| `issue_refund(order_id, refund_inr)` | Appends a timestamped JSON line to `outputs/refund_ledger.jsonl` |
| `escalate_to_human(order_id, refund_inr)` | Appends a timestamped JSON line to `outputs/refund_ledger.jsonl` |

### ReAct loop: seven scenarios

`run_agent(user_message, scenario_id, max_iterations=6, token_limit=6000, time_limit_seconds=10)`. Each run is appended to `outputs/agent_runs.jsonl` with every step's tool, arguments and observation.

| scenario | expected | status | refund (INR) | model calls | tokens used |
|---|---|---|---|---|---|
| S1 | REFUND | REFUND | 128.25 | 5 | 1,142 |
| S2 | REFUND | REFUND | 135.00 | 5 | 1,142 |
| S3 | ESCALATE | ESCALATE | 1,999.00 | 5 | 1,129 |
| S4 | DENIED | DENIED | 0.00 | 4 | 801 |
| S5 | DENIED | DENIED | 0.00 | 3 | 484 |
| S6 | NOT_FOUND | NOT_FOUND | 0.00 | 2 | 170 |
| S7 | FALLBACK | FALLBACK_MAX_ITERATIONS | 0.00 | 6 | 3,294 |

S7 (`[LOOP]`) keeps requesting `search_policy` and stops after all six model calls, well inside the 6,000-token limit.

### Stop-safely demonstrations

| demo | status | model calls | final answer |
|---|---|---|---|
| S1 with `token_limit=200` | **FALLBACK_TOKEN_LIMIT** | 3 (501 tokens). The third reply's tool was not executed | "Handing over to a human agent (token limit 200 exceeded (501 used)). Steps completed: get_order -> search_policy." |
| S1 with `time_limit_seconds=0` | **FALLBACK_TIMEOUT** | 0. Stopped before the first call | "Handing over to a human agent (time limit reached). Steps completed: no tools." |

### Crash and resume

After every tool observation, `state/<run_id>.json` is written. It holds the run id, scenario id, full message list, tokens_used, step number and the tools already executed. For the demo, S1 raises a simulated crash right after its second tool, once that checkpoint is saved. `resume_agent("S1-crash-resume")` then reloads the checkpoint and continues.

Tools executed across the crash and the resume, in order:
1. get_order
2. search_policy (simulated crash here)
3. calculate_refund (after the resume)
4. issue_refund

Four executions, none repeated. Final status **REFUND, INR 128.25**.

### ReAct versus plan-and-execute

Our ReAct agent asks the model once per step: 5 calls for S1 (1,142 tokens), 3 for S5 and 2 for S6. Each call resends the growing message history, including policy passages, so tokens grow faster than linearly with steps.

A plan-and-execute design asks once for the full plan (get_order → search_policy → calculate_refund → issue_refund), runs the tools without the model, and calls it again only to replan or write the final answer. S1 would need about 2 calls and far fewer tokens.

The difference shows on unexpected observations:
- In S6 `get_order` returns NOT_FOUND, and in S5 the order is cancelled. ReAct sees each observation before deciding, so it stops after 2 and 3 calls without wasted tools.
- A fixed plan would carry on into calculate_refund unless the executor detects the error and triggers a replan, which costs an extra call and needs hand-written failure checks.
- A plan also cannot react to the refund amount: issue_refund versus escalate_to_human depends on a value known only mid-run.

For this refund workflow, the steps are short (2 to 5) and branch on every observation, the money-moving action depends on intermediate results, and the cost is small (about 1,100 tokens). So we choose **ReAct**, with the hard limits above as the safety net. Plan-and-execute would pay off for long, predictable pipelines where per-step model calls dominate the cost.

## Limitations and Next Steps

- **Premium flag is post-hoc:** it comes from whole-window RFM that includes the September lapse window, so the retention list is illustrative and not a leakage-free evaluation. Next: recompute segments as of the 2025-09-01 cutoff before scoring.
- **The mock model is a keyword matcher.** Accuracy, token counts and the agent's decisions reflect `mock_llm.py`, not a real LLM. A hosted model would need the same guardrails plus evaluation on real, messier tickets.
- **TF-IDF retrieval** misses paraphrases and synonyms. Answers are single extracted sentences that may repeat overlapping chunk text. Next: sentence-aware chunking and embedding-based or hybrid retrieval.
- **The lapse model** uses one six-month window and a fixed 0.5 threshold. Our logistic regression selected C=100 rather than the reference C=1. Next: tune the threshold for the retention team's cost ratio, calibrate probabilities, and validate on a later month.
- **Imputation:** city-median ages and category-median delivery times smooth out real variation. Imputed values could be flagged in an extra column.
- **The refund ledger** has wall-clock timestamps, so it is not byte-identical across runs; the decisions are. Each simulated request is treated as being inside the 7-day refund window, and there is no idempotency key, so re-running issues the refund line again. Next: a ledger keyed on order_id that refuses duplicates.
- **Environment:** `requirements.txt` was frozen on macOS with Python 3.11, the minimum the brief allows, so it also installs on newer versions. Results were verified there; other platforms should match within the brief's tolerances.
