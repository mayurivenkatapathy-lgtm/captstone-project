**Input guardrails:** 4 empty tickets (skipped_empty), 4 long tickets (flagged_long, est_tokens = [734]) -- none of them is sent to the model.

**PII redaction over all 164 tickets**

| PII type | substitutions |
|---|---|
| email | 55 |
| phone | 91 |
| order_id | 132 |
| total | 278 |
| left after re-applying patterns | 0 |

**Retries (zero-shot full run):** 19 TransientLLMErrors, all recovered; retry numbers used [0]; waits 0.0453-0.0562 s.

**Status counts (zero-shot full run)**

| status | tickets |
|---|---|
| classified_json | 135 |
| classified_keyword | 12 |
| flagged_invalid_output | 9 |
| skipped_empty | 4 |
| flagged_long | 4 |

**Zero-shot vs few-shot (no budget)**

| prompt | classified | accuracy | total tokens | tokens / classified | retries |
|---|---|---|---|---|---|
| zero-shot | 147 | 85.7% (126/147) | 11428 | 77.70 | 19 |
| few-shot | 147 | 100.0% (147/147) | 21256 | 144.60 | 19 |

System prompt size: zero-shot 45 est. tokens, few-shot 108 est. tokens.

**Zero-shot confusion table (rows = true, columns = predicted)**

| true \ predicted | billing | delivery | fraud | technical |
|---|---|---|---|---|
| billing | 38 | 0 | 0 | 0 |
| delivery | 0 | 36 | 0 | 0 |
| fraud | 11 | 0 | 23 | 0 |
| technical | 10 | 0 | 0 | 29 |

**Budget demo:** zero-shot, TOKEN_BUDGET = 6000: 74 tickets budget_exhausted (tokens spent 6021) -> outputs/triage_budget_demo.csv

**Final routing (few-shot, TOKEN_BUDGET = 100000, 21256 tokens) -> outputs/triage_results.csv**

| route | priority | tickets |
|---|---|---|
| human_review | NORMAL | 17 |
| premium_desk | HIGH | 11 |
| security_team | HIGH | 34 |
| support_queue | NORMAL | 102 |

**Final status counts**

| status | tickets |
|---|---|
| classified_json | 135 |
| classified_keyword | 12 |
| flagged_invalid_output | 9 |
| skipped_empty | 4 |
| flagged_long | 4 |

