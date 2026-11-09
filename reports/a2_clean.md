**Cleaning rules and rows/values changed**

| table | rule | changed |
|---|---|---|
| customers | city: strip spaces + title case | 476 |
| customers | gender: map spellings to male/female, blank -> unknown | 950 |
| customers | age: outside 10-100 -> missing | 6 |
| customers | age: fill missing with city median (groupby + transform) | 67 |
| customers | signup_date: parse to datetime | 1200 |
| orders | 1. order_ts: parse to datetime | 13084 |
| orders | 2. drop exact duplicate rows | 119 |
| orders | 3. keep latest order_ts per order_id (drops earlier pending records) | 656 |
| orders | 4. order_amount: unparseable -> recomputed from price x qty x (1 - discount) | 112 |
| orders | 5a. delivery_minutes: negative -> missing | 105 |
| orders | 5b. delivery_minutes: completed + missing -> category median of completed orders | 774 |
| orders | 5c. delivery_minutes: cancelled orders left missing (never delivered) | 1199 |

**After cleaning**

| item | value |
|---|---|
| cities | Pune 227, Delhi 210, Bengaluru 197, Chennai 191, Hyderabad 191, Mumbai 184 |
| genders | female 610, male 560, unknown 30 |
| missing ages / age range | 0 / 18-60 |
| order rows / distinct order_id | 12,309 / 12,309 |
| status counts | completed 11,110, cancelled 1,199 |
| missing order_amount | 0 |
| missing delivery_minutes (completed / cancelled) | 0 / 1,199 |
| sum of completed order_amount | INR 2,998,668.80 |

