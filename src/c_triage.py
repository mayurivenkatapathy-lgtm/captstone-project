"""Part C -- support-ticket triage: input guardrails, PII redaction, retries, output validation,
token budget and segment-aware routing around the supplied mock_llm.py."""
import json
import os
import random
import re
import time

import pandas as pd

from config import OUTPUTS, RAW, SEED, Report  # also puts the repo root (mock_llm.py) on sys.path
import mock_llm  # noqa: E402

MAX_INPUT_TOKENS = 400
BASE_DELAY = 0.05
MAX_RETRIES = 3
CATEGORIES = ["billing", "delivery", "technical", "fraud"]
PII_PATTERNS = [("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
                ("phone", re.compile(r"\b[6-9]\d{9}\b"), "[PHONE]"),
                ("order_id", re.compile(r"ORD-\d{6}"), "[ORDER_ID]")]

ZERO_SHOT = """You are a support-ticket triage model. CLASSIFY the customer ticket into exactly one category.
Allowed categories: billing, delivery, technical, fraud.
Reply with JSON only, no other text: {"category": "<one allowed category>", "reason": "<short reason>"}"""

FEW_SHOT = ZERO_SHOT + """
EXAMPLES:
Ticket: Someone used my card for an order I never placed. -> {"category": "fraud", "reason": "unauthorized transaction"}
Ticket: The app shows an error when I open the cart. -> {"category": "technical", "reason": "app error"}
Ticket: I was charged twice for one order. -> {"category": "billing", "reason": "double charge"}"""


def redact(text):
    """Apply the three PII patterns in order; return (redacted_text, {type: substitutions})."""
    counts = {}
    for name, pat, placeholder in PII_PATTERNS:
        text, counts[name] = pat.subn(placeholder, text)
    return text, counts


def call_with_retry(messages, ticket_id, log):
    """Call the model, retrying TransientLLMError up to MAX_RETRIES times with exponential backoff + jitter."""
    for n in range(MAX_RETRIES + 1):
        try:
            return mock_llm.chat(messages), n
        except mock_llm.TransientLLMError as e:
            if n == MAX_RETRIES:
                raise
            wait = BASE_DELAY * 2 ** n * random.uniform(0.9, 1.15)
            log.append((ticket_id, n, round(wait, 4)))
            print(f"retry ticket={ticket_id} retry_no={n} wait={wait:.4f}s ({e})")
            time.sleep(wait)


def validate(reply):
    """Return (status, category). JSON first, then a single allowed keyword, otherwise flag for humans."""
    try:
        data = json.loads(reply)
        if isinstance(data, dict) and data.get("category") in CATEGORIES:
            return "classified_json", data["category"]
        return "flagged_invalid_output", ""
    except (json.JSONDecodeError, TypeError):
        found = {w for w in re.findall(r"[a-z]+", (reply or "").lower()) if w in CATEGORIES}
        if len(found) == 1:
            return "classified_keyword", found.pop()
        return "flagged_invalid_output", ""


def run_pipeline(tickets, system_prompt, token_budget=None):
    """Triage every ticket in file order. Returns (results DataFrame, retry log, total tokens)."""
    mock_llm.reset()
    random.seed(SEED)
    rows, log, total = [], [], 0
    for t in tickets.itertuples(index=False):
        row = {"ticket_id": t.ticket_id, "customer_id": t.customer_id, "true_category": t.true_category,
               "status": "", "category": "", "tokens_used": 0}
        if not t.text.strip():
            row["status"] = "skipped_empty"
        elif mock_llm.est_tokens(t.text) > MAX_INPUT_TOKENS:
            row["status"] = "flagged_long"
        elif token_budget is not None and total >= token_budget:
            row["status"] = "budget_exhausted"
        else:
            clean, _ = redact(t.text)
            assert not any(p.search(clean) for _, p, _ in PII_PATTERNS), f"PII left in prompt for {t.ticket_id}"
            resp, _ = call_with_retry([{"role": "system", "content": system_prompt},
                                       {"role": "user", "content": clean}], t.ticket_id, log)
            row["tokens_used"] = resp.usage.total_tokens
            total += resp.usage.total_tokens
            row["status"], row["category"] = validate(resp.choices[0].message.content)
        rows.append(row)
    return pd.DataFrame(rows), log, total


def route(df, segments):
    seg = segments.set_index("customer_id")
    df["segment_name"] = df["customer_id"].map(seg["segment_name"]).fillna("")
    premium = df["customer_id"].map(seg["is_premium"]).fillna(False).astype(bool)
    human = df["status"].isin(["skipped_empty", "flagged_long", "flagged_invalid_output", "budget_exhausted"])
    df["route"] = "support_queue"
    df["priority"] = "NORMAL"
    df.loc[premium, ["route", "priority"]] = ["premium_desk", "HIGH"]
    df.loc[df["category"] == "fraud", ["route", "priority"]] = ["security_team", "HIGH"]
    df.loc[human, ["route", "priority"]] = ["human_review", "NORMAL"]
    return df


COLUMNS = ["ticket_id", "customer_id", "status", "category", "segment_name", "priority", "route", "tokens_used"]

if __name__ == "__main__":
    rep = Report("c_triage")
    tickets = pd.read_csv(os.path.join(RAW, "tickets.csv"), keep_default_na=False, dtype=str)
    segments = pd.read_csv(os.path.join(OUTPUTS, "customer_segments.csv"))

    # task 1: input guardrails
    empty = tickets["text"].str.strip() == ""
    long_tokens = tickets.loc[~empty, "text"].map(mock_llm.est_tokens)
    long = long_tokens[long_tokens > MAX_INPUT_TOKENS]
    rep.add(f"**Input guardrails:** {int(empty.sum())} empty tickets (skipped_empty), {len(long)} long tickets "
            f"(flagged_long, est_tokens = {sorted(set(long))}) -- none of them is sent to the model.\n")

    # task 2: redaction counts over all 164 tickets, then prove nothing is left
    totals = {name: 0 for name, _, _ in PII_PATTERNS}
    redacted = []
    for text in tickets["text"]:
        clean, c = redact(text)
        redacted.append(clean)
        for k, v in c.items():
            totals[k] += v
    leftover = sum(len(p.findall(t)) for t in redacted for _, p, _ in PII_PATTERNS)
    red = pd.DataFrame([(k, v) for k, v in totals.items()] + [("total", sum(totals.values())),
                                                              ("left after re-applying patterns", leftover)],
                       columns=["PII type", "substitutions"])
    rep.table("PII redaction over all 164 tickets", red)

    # tasks 4-6: full zero-shot and few-shot runs (no budget)
    runs = {}
    for name, prompt in [("zero-shot", ZERO_SHOT), ("few-shot", FEW_SHOT)]:
        df, log, total = run_pipeline(tickets, prompt)
        runs[name] = (df, log, total)
    zs, zs_log, _ = runs["zero-shot"]
    status = zs["status"].value_counts()
    rep.add(f"**Retries (zero-shot full run):** {len(zs_log)} TransientLLMErrors, all recovered; "
            f"retry numbers used {sorted({n for _, n, _ in zs_log})}; waits "
            f"{min(w for *_, w in zs_log):.4f}-{max(w for *_, w in zs_log):.4f} s.\n")
    rep.table("Status counts (zero-shot full run)", status.rename_axis("status").reset_index(name="tickets"))

    cmp_rows = []
    for name, (df, log, total) in runs.items():
        ok = df[df["status"].isin(["classified_json", "classified_keyword"])]
        acc = (ok["category"] == ok["true_category"]).mean()
        cmp_rows.append((name, len(ok), f"{acc:.1%} ({(ok['category'] == ok['true_category']).sum()}/{len(ok)})",
                         total, round(total / len(ok), 1), len(log)))
    rep.table("Zero-shot vs few-shot (no budget)", pd.DataFrame(
        cmp_rows, columns=["prompt", "classified", "accuracy", "total tokens", "tokens / classified", "retries"]))
    rep.add(f"System prompt size: zero-shot {mock_llm.est_tokens(ZERO_SHOT)} est. tokens, "
            f"few-shot {mock_llm.est_tokens(FEW_SHOT)} est. tokens.\n")
    ok = zs[zs["status"].isin(["classified_json", "classified_keyword"])]
    conf = pd.crosstab(ok["true_category"], ok["category"]).reset_index().rename(columns={"true_category": "true \\ predicted"})
    rep.table("Zero-shot confusion table (rows = true, columns = predicted)", conf)

    # task 7a: token budget demo
    BUDGET_DEMO = 6000
    demo, _, demo_total = run_pipeline(tickets, ZERO_SHOT, token_budget=BUDGET_DEMO)
    demo = route(demo, segments)
    demo[COLUMNS].to_csv(os.path.join(OUTPUTS, "triage_budget_demo.csv"), index=False)
    n_exh = int((demo["status"] == "budget_exhausted").sum())
    rep.add(f"**Budget demo:** zero-shot, TOKEN_BUDGET = {BUDGET_DEMO}: {n_exh} tickets budget_exhausted "
            f"(tokens spent {demo_total}) -> outputs/triage_budget_demo.csv\n")

    # task 7b: final few-shot run with routing
    final, _, final_total = run_pipeline(tickets, FEW_SHOT, token_budget=100000)
    final = route(final, segments)
    final[COLUMNS].to_csv(os.path.join(OUTPUTS, "triage_results.csv"), index=False)
    rt = final.groupby(["route", "priority"]).size().reset_index(name="tickets")
    rep.table(f"Final routing (few-shot, TOKEN_BUDGET = 100000, {final_total} tokens) -> outputs/triage_results.csv", rt)
    rep.table("Final status counts", final["status"].value_counts().rename_axis("status").reset_index(name="tickets"))
    rep.save()

    assert empty.sum() == 4 and len(long) == 4 and set(long) == {734}
    assert totals == {"email": 55, "phone": 91, "order_id": 132} and leftover == 0
    assert len(zs_log) == 19 and all(n == 0 and 0.045 <= w <= 0.0575 for _, n, w in zs_log)
    assert (status.get("classified_json"), status.get("classified_keyword"), status.get("flagged_invalid_output")) == (135, 12, 9)
    assert n_exh >= 1 and len(final) == 164
