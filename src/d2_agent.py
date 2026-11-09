"""Part D tasks 5-8 -- refund agent: tools + TOOL_MAP, ReAct loop with safe stops, checkpoint/resume."""
import json
import os
import sqlite3
import time
from datetime import datetime

import pandas as pd

from config import DB_PATH, OUTPUTS, RAW, STATE, Report
import mock_llm  # noqa: E402  (repo root put on sys.path by config)
from d1_rag import retrieve

LEDGER = os.path.join(OUTPUTS, "refund_ledger.jsonl")
RUNS = os.path.join(OUTPUTS, "agent_runs.jsonl")
AGENT_SYSTEM = ("You are the Instamart refund AGENT. Decide refund requests by calling tools: look up the order, "
                "check the refund policy, calculate the refund, then issue it or escalate it to a human. "
                "Finish with one line that starts with REFUND, ESCALATE, DENIED or NOT_FOUND and a colon.")
_current_run = {"run_id": None}   # lets ledger lines name the run that wrote them


# ---------------- tools ----------------
def get_order(order_id):
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute("SELECT order_id, status, order_amount, delivery_minutes FROM orders WHERE order_id = ?",
                          (order_id,)).fetchone()
    if row is None:
        return {"error": "order not found"}
    return {"order_id": row[0], "status": row[1], "order_amount": row[2], "delivery_minutes": row[3]}


def search_policy(query):
    return {"results": retrieve(query, k=3)}


def calculate_refund(order_amount, delivery_minutes):
    """Full refund when delivered in more than 45 minutes, otherwise nothing."""
    if delivery_minutes is None or float(delivery_minutes) <= 45:
        return {"refund_inr": 0.0}
    return {"refund_inr": round(float(order_amount), 2)}


def _ledger(tool, order_id, refund_inr):
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": datetime.now().isoformat(timespec="seconds"), "tool": tool,
                            "run_id": _current_run["run_id"], "order_id": order_id,
                            "refund_inr": refund_inr}) + "\n")
    return {"refund_inr": refund_inr}


def issue_refund(order_id, refund_inr):
    return _ledger("issue_refund", order_id, refund_inr)


def escalate_to_human(order_id, refund_inr):
    return _ledger("escalate_to_human", order_id, refund_inr)


TOOLS_SPEC = [
    {"name": "get_order", "description": "Look up one order in the Instamart database by its order id.",
     "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}},
    {"name": "search_policy", "description": "Retrieve the three policy passages most relevant to a query.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "calculate_refund", "description": "Compute the refund in INR from the order amount and delivery minutes.",
     "parameters": {"type": "object", "properties": {"order_amount": {"type": "number"},
                                                     "delivery_minutes": {"type": "number"}},
                    "required": ["order_amount", "delivery_minutes"]}},
    {"name": "issue_refund", "description": "Issue an approved refund of at most INR 1000 and record it in the ledger.",
     "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}, "refund_inr": {"type": "number"}},
                    "required": ["order_id", "refund_inr"]}},
    {"name": "escalate_to_human", "description": "Send a refund above INR 1000 to a human support lead for approval.",
     "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}, "refund_inr": {"type": "number"}},
                    "required": ["order_id", "refund_inr"]}},
]
TOOL_MAP = {"get_order": get_order, "search_policy": search_policy, "calculate_refund": calculate_refund,
            "issue_refund": issue_refund, "escalate_to_human": escalate_to_human}


# ---------------- agent loop ----------------
class SimulatedCrash(Exception):
    pass


def _checkpoint_path(run_id):
    return os.path.join(STATE, f"{run_id}.json")


def _save_checkpoint(st):
    with open(_checkpoint_path(st["run_id"]), "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)


def _handoff(st, reason):
    done = " -> ".join(s["tool"] for s in st["steps"]) or "no tools"
    return f"Handing over to a human agent ({reason}). Steps completed: {done}."


def _finish(st, status, final_answer):
    st.update(status=status, final_answer=final_answer)
    _save_checkpoint(st)
    return {k: st[k] for k in ("run_id", "scenario_id", "status", "final_answer", "steps", "llm_calls",
                               "tokens_used", "tools_executed")}


def _loop(st, crash_after_tools=None):
    _current_run["run_id"] = st["run_id"]
    started = time.monotonic()
    lim = st["limits"]
    while True:
        if time.monotonic() - started >= lim["time_limit_seconds"]:
            return _finish(st, "FALLBACK_TIMEOUT", _handoff(st, "time limit reached"))
        if st["llm_calls"] >= lim["max_iterations"]:
            return _finish(st, "FALLBACK_MAX_ITERATIONS", _handoff(st, f"no answer after {st['llm_calls']} model calls"))

        resp = mock_llm.chat(st["messages"], tools=TOOLS_SPEC)
        st["llm_calls"] += 1
        st["tokens_used"] += resp.usage.total_tokens
        msg = resp.choices[0].message
        if st["tokens_used"] > lim["token_limit"]:
            return _finish(st, "FALLBACK_TOKEN_LIMIT",
                           _handoff(st, f"token limit {lim['token_limit']} exceeded ({st['tokens_used']} used)"))
        if not msg.tool_calls:
            return _finish(st, msg.content.split(":", 1)[0].strip(), msg.content)

        tc = msg.tool_calls[0]
        st["messages"].append({"role": "assistant", "content": None,
                               "tool_calls": [{"id": tc.id, "name": tc.name, "arguments": tc.arguments}]})
        observation = TOOL_MAP[tc.name](**tc.arguments)
        st["messages"].append({"role": "tool", "tool_call_id": tc.id, "name": tc.name,
                               "content": json.dumps(observation)})
        st["step"] += 1
        st["tools_executed"].append(tc.name)
        st["steps"].append({"step": st["step"], "tool": tc.name, "arguments": tc.arguments, "observation": observation})
        _save_checkpoint(st)
        if crash_after_tools is not None and len(st["tools_executed"]) == crash_after_tools:
            raise SimulatedCrash(f"simulated crash after tool #{crash_after_tools} ({tc.name})")


def run_agent(user_message, scenario_id, max_iterations=6, token_limit=6000, time_limit_seconds=10,
              run_id=None, crash_after_tools=None):
    st = {"run_id": run_id or scenario_id, "scenario_id": scenario_id,
          "messages": [{"role": "system", "content": AGENT_SYSTEM}, {"role": "user", "content": user_message}],
          "tokens_used": 0, "llm_calls": 0, "step": 0, "tools_executed": [], "steps": [],
          "status": "RUNNING", "final_answer": None,
          "limits": {"max_iterations": max_iterations, "token_limit": token_limit,
                     "time_limit_seconds": time_limit_seconds}}
    return _loop(st, crash_after_tools)


def resume_agent(run_id):
    """Reload the last checkpoint of run_id and continue from its saved message list."""
    with open(_checkpoint_path(run_id), encoding="utf-8") as f:
        st = json.load(f)
    return _loop(st)


def refund_amount(result):
    for s in result["steps"]:
        if s["tool"] in ("issue_refund", "escalate_to_human"):
            return s["observation"]["refund_inr"]
    return 0.0


def log_run(result, label):
    with open(RUNS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"run": label, **{k: result[k] for k in ("run_id", "scenario_id", "status", "final_answer",
                                                                    "llm_calls", "tokens_used", "steps")}}) + "\n")


if __name__ == "__main__":
    rep = Report("d2_agent")
    for path in (LEDGER, RUNS):
        if os.path.exists(path):
            os.remove(path)
    for fn in os.listdir(STATE):
        if fn.endswith(".json"):
            os.remove(os.path.join(STATE, fn))

    # task 6: the seven scenarios
    sc = pd.read_csv(os.path.join(RAW, "agent_scenarios.csv"), dtype={"expected_refund_inr": float})
    rows = []
    for s in sc.itertuples(index=False):
        res = run_agent(s.message, s.scenario_id)
        log_run(res, "scenario")
        amt = refund_amount(res)
        ok = (res["status"] == s.expected_outcome or (s.expected_outcome == "FALLBACK"
                                                      and res["status"] == "FALLBACK_MAX_ITERATIONS"))
        ok = ok and abs(amt - s.expected_refund_inr) <= 0.01
        rows.append((s.scenario_id, s.expected_outcome, res["status"], f"{amt:,.2f}", res["llm_calls"],
                     res["tokens_used"], " -> ".join(res["tools_executed"]), "yes" if ok else "NO"))
    tbl = pd.DataFrame(rows, columns=["scenario", "expected", "status", "refund INR", "model calls", "tokens used",
                                      "tools executed", "match"])
    rep.table("Seven refund scenarios (max_iterations=6, token_limit=6000, time_limit_seconds=10)", tbl)

    # task 7: stop-safely demonstrations
    s1 = sc.iloc[0]
    tok = run_agent(s1.message, "S1", token_limit=200, run_id="S1-token-limit-demo")
    log_run(tok, "demo token_limit=200")
    tmo = run_agent(s1.message, "S1", time_limit_seconds=0, run_id="S1-timeout-demo")
    log_run(tmo, "demo time_limit_seconds=0")
    rep.table("Stop-safely demonstrations", pd.DataFrame([
        ("S1 with token_limit=200", tok["status"], tok["llm_calls"], tok["tokens_used"], tok["final_answer"]),
        ("S1 with time_limit_seconds=0", tmo["status"], tmo["llm_calls"], tmo["tokens_used"], tmo["final_answer"]),
    ], columns=["demo", "status", "model calls", "tokens used", "final answer (handoff summary)"]))

    # task 8: crash after the second tool, then resume from the checkpoint
    try:
        run_agent(s1.message, "S1", run_id="S1-crash-resume", crash_after_tools=2)
        raise AssertionError("crash did not happen")
    except SimulatedCrash as e:
        crash_msg = str(e)
    before = json.load(open(_checkpoint_path("S1-crash-resume")))["tools_executed"]
    resumed = resume_agent("S1-crash-resume")
    log_run(resumed, "crash + resume")
    rep.add(f"**Crash and resume (S1):** {crash_msg}. Tools before crash: {', '.join(before)}. "
            f"Tools across crash + resume: {', '.join(resumed['tools_executed'])} "
            f"({len(resumed['tools_executed'])} executions). Final: {resumed['status']} "
            f"INR {refund_amount(resumed):.2f}; checkpoint state/S1-crash-resume.json.\n")
    rep.save()

    assert (tbl["match"] == "yes").all()
    assert tbl.loc[0, "model calls"] == 5 and tbl.loc[6, "model calls"] == 6
    assert tok["status"] == "FALLBACK_TOKEN_LIMIT" and tmo["status"] == "FALLBACK_TIMEOUT" and tmo["llm_calls"] == 0
    assert resumed["tools_executed"] == ["get_order", "search_policy", "calculate_refund", "issue_refund"]
    assert resumed["status"] == "REFUND" and refund_amount(resumed) == 128.25
