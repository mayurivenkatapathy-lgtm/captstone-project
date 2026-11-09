**Seven refund scenarios (max_iterations=6, token_limit=6000, time_limit_seconds=10)**

| scenario | expected | status | refund INR | model calls | tokens used | tools executed | match |
|---|---|---|---|---|---|---|---|
| S1 | REFUND | REFUND | 128.25 | 5 | 1142 | get_order -> search_policy -> calculate_refund -> issue_refund | yes |
| S2 | REFUND | REFUND | 135.00 | 5 | 1142 | get_order -> search_policy -> calculate_refund -> issue_refund | yes |
| S3 | ESCALATE | ESCALATE | 1,999.00 | 5 | 1129 | get_order -> search_policy -> calculate_refund -> escalate_to_human | yes |
| S4 | DENIED | DENIED | 0.00 | 4 | 801 | get_order -> search_policy -> calculate_refund | yes |
| S5 | DENIED | DENIED | 0.00 | 3 | 484 | get_order -> search_policy | yes |
| S6 | NOT_FOUND | NOT_FOUND | 0.00 | 2 | 170 | get_order | yes |
| S7 | FALLBACK | FALLBACK_MAX_ITERATIONS | 0.00 | 6 | 3294 | search_policy -> search_policy -> search_policy -> search_policy -> search_policy -> search_policy | yes |

**Stop-safely demonstrations**

| demo | status | model calls | tokens used | final answer (handoff summary) |
|---|---|---|---|---|
| S1 with token_limit=200 | FALLBACK_TOKEN_LIMIT | 3 | 501 | Handing over to a human agent (token limit 200 exceeded (501 used)). Steps completed: get_order -> search_policy. |
| S1 with time_limit_seconds=0 | FALLBACK_TIMEOUT | 0 | 0 | Handing over to a human agent (time limit reached). Steps completed: no tools. |

**Crash and resume (S1):** simulated crash after tool #2 (search_policy). Tools before crash: get_order, search_policy. Tools across crash + resume: get_order, search_policy, calculate_refund, issue_refund (4 executions). Final: REFUND INR 128.25; checkpoint state/S1-crash-resume.json.

