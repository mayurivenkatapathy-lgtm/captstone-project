**SQL results vs reference**

| query | result | ours | reference |
|---|---|---|---|
| Q1 | customers with >INR 8000 in completed orders above INR 500 | 30 | 30 |
| Q2 | rows / sum of revenue | 30 / INR 2,998,668.80 | 30 / INR 2,998,668.80 |
| Q2 | largest cell | Bengaluru / Electronics INR 233,909.45 | Bengaluru / Electronics INR 233,909.45 |
| Q3 | products above average price | 11 | 11 |
| Q4 | customers without a completed order | 25 | 25 |
| Q5 | customers above average / average spend | 550 / INR 2,552.06 | 550 / INR 2,552.06 |
| Q6 | rows where RANK() != ROW_NUMBER() | 8 | 8 |
| Q7 | daily rows / last cumulative | 183 / INR 2,998,668.80 | 183 / INR 2,998,668.80 |

**Q6 -- top customer per city**

| city | customer_id | total_spend |
|---|---|---|
| Bengaluru | C0082 | 12,856.20 |
| Chennai | C0930 | 10,151.40 |
| Delhi | C0291 | 13,742.60 |
| Hyderabad | C0743 | 12,730.05 |
| Mumbai | C0693 | 14,766.55 |
| Pune | C0426 | 10,377.10 |

**Q6 -- rows where ties make RANK() differ from ROW_NUMBER()**

| city | customer_id | total_spend | rnk | dense_rnk | row_num |
|---|---|---|---|---|---|
| Bengaluru | C0734 | 2,598.00 | 99 | 99 | 100 |
| Bengaluru | C0723 | 135.00 | 179 | 178 | 180 |
| Mumbai | C1053 | 396.00 | 149 | 149 | 150 |
| Mumbai | C0608 | 280.00 | 160 | 159 | 161 |
| Pune | C1064 | 3,236.95 | 74 | 74 | 75 |
| Pune | C0057 | 285.00 | 189 | 188 | 190 |
| Pune | C0936 | 285.00 | 189 | 188 | 191 |
| Pune | C0276 | 114.00 | 209 | 206 | 210 |

