### Raw table profiles

**customers.csv -- shape 1,200 rows x 5 columns**

| column | dtype | missing | missing_pct |
|---|---|---|---|
| customer_id | str | 0 | 0.00 |
| city | str | 0 | 0.00 |
| signup_date | str | 0 | 0.00 |
| age | float64 | 61 | 5.08 |
| gender | str | 30 | 2.50 |

**products.csv -- shape 40 rows x 4 columns**

| column | dtype | missing | missing_pct |
|---|---|---|---|
| product_id | str | 0 | 0.00 |
| product_name | str | 0 | 0.00 |
| category | str | 0 | 0.00 |
| price_inr | int64 | 0 | 0.00 |

**orders.csv -- shape 13,084 rows x 9 columns**

| column | dtype | missing | missing_pct |
|---|---|---|---|
| order_id | str | 0 | 0.00 |
| customer_id | str | 0 | 0.00 |
| product_id | str | 0 | 0.00 |
| quantity | int64 | 0 | 0.00 |
| order_ts | str | 0 | 0.00 |
| status | str | 0 | 0.00 |
| discount_pct | int64 | 0 | 0.00 |
| order_amount | str | 0 | 0.00 |
| delivery_minutes | float64 | 2541 | 19.42 |

**Audit figures**

| check | value | reference | match |
|---|---|---|---|
| raw orders.csv rows | 13084 | 13084 | yes |
| exact duplicate rows | 119 | 119 | yes |
| rows with status pending | 656 | 656 | yes |
| distinct order_id | 12309 | 12309 | yes |
| non-numeric order_amount | 120 | 120 | yes |
| negative delivery_minutes | 106 | 106 | yes |
| blank delivery_minutes | 2541 | 2541 | yes |
| blank age | 61 | 61 | yes |
| age outside 10-100 | 6 | 6 | yes |
| distinct raw city spellings | 24 | 24 | yes |
| distinct non-blank raw gender spellings | 10 | 10 | yes |
| blank gender | 30 | 30 | yes |

