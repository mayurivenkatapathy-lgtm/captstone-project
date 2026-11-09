**Chunking (40 words, overlap 10):** 15 chunks -- refund_policy.txt 4, delivery_policy.txt 3, escalation_policy.txt 3, payment_policy.txt 3, privacy_policy.txt 2

**retrieve('refund policy late delivery', k=3)**

| source | score | text (start) |
|---|---|---|
| refund_policy.txt | 0.2719 | order is delivered in more than 45 minutes, the customer rec... |
| refund_policy.txt | 0.2514 | Refund Policy. A refund can be requested only for orders who... |
| refund_policy.txt | 0.2454 | late-delivery refund is paid. Refunds up to INR 1000 are app... |

**Policy evaluation (14 questions)**

| chunking | expected doc in top 3 (12 answerable) | answer contains expected fact | fallback on 2 unanswerable |
|---|---|---|---|
| 40 words, overlap 10 | 12/12 | 12/12 | 2/2 |
| 40 words, overlap 0 | 12/12 | 10/12 | 2/2 |

**Questions that fail with overlap 0**

| question | expected_doc | doc_in_top3 | fact_in_answer | answer |
|---|---|---|---|---|
| What delivery time makes a completed order eligible for a full refund? | refund_policy.txt | True | False | receives a full refund of the order amount. |
| How soon is money returned when a payment fails but is deducted? | payment_policy.txt | True | False | If a payment fails but money is deducted, the amount is returned automatically   1000 must be approved by a human support lead before money is returned. |

**Answers with overlap 10**

| question | answer |
|---|---|
| What delivery time makes a completed order eligible for a full refund? | order is delivered in more than 45 minutes, the customer receives a full refund of the order amount. |
| Who must approve a refund above INR 1000? | A refund above INR 1000 must be approved by a human support lead before money is returned. |
| How many days do I have to raise a refund request? | A refund request must be raised within 7 days of the delivery date. |
| What is the delivery fee on small orders? | A delivery fee of INR 25 is charged on orders below INR 199,   of INR 25 is charged on orders below INR 199, and delivery is free on orders of INR 199 or more. |
| On orders of what value is delivery free? | of INR 25 is charged on orders below INR 199, and delivery is free on orders of INR 199 or more. |
| Why does the electronics delivery need a one time password? | Electronics items are delivered only after the customer shares a one time password with the rider. |
| Is cash on delivery available for a large order? | Cash on delivery is available only for orders up to INR 2500. |
| How soon is money returned when a payment fails but is deducted? | If a payment fails but money is deducted, the amount is returned automatically   fails but money is deducted, the amount is returned automatically within 48 hours. |
| Can wallet balance be refunded as cash? | Wallet balance can be used for any order and is never refunded as cash. |
| When are delivery addresses deleted from active systems? | Delivery addresses are deleted from active systems 180 days after   Delivery addresses are deleted from active systems 180 days after the last order. |
| How fast must a fraud ticket reach the security team? | A ticket about fraud or an unauthorized transaction is marked high priority and sent to the security team within 2 hours. |
| After how many steps must an automated assistant hand over to a human? | If an automated assistant cannot resolve a ticket within 6 steps, it must hand the case to a human agent with a short summary. |
| What is the favourite colour of the company mascot? | I could not find that information in the policy documents. |
| Who won the cricket world cup final? | I could not find that information in the policy documents. |

