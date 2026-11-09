"""Part D tasks 1-4 -- chunk the policy documents, TF-IDF retrieval, grounded answers, evaluation.
The refund agent (d2_agent.py) imports retrieve() from here."""
import os

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import POLICIES, RAW, Report
import mock_llm  # noqa: E402  (repo root put on sys.path by config)

CHUNK_WORDS, OVERLAP = 40, 10
POLICY_SYSTEM = ("You are the Instamart POLICY ASSISTANT. Answer the question using only the CONTEXT supplied. "
                 "If the answer is not in the context, say: I could not find that information in the policy documents.")


def chunk_documents(size=CHUNK_WORDS, overlap=OVERLAP, folder=POLICIES):
    """Split each .txt file into word windows of `size` that step by size - overlap; stop once a window
    reaches the document's last word. Returns [{"source", "text"}]."""
    chunks = []
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith(".txt"):
            continue
        words = open(os.path.join(folder, fn), encoding="utf-8").read().split()
        start = 0
        while True:
            chunks.append({"source": fn, "text": " ".join(words[start:start + size])})
            if start + size >= len(words):
                break
            start += size - overlap
    return chunks


class Retriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer()
        self.matrix = self.vectorizer.fit_transform([c["text"] for c in chunks])

    def retrieve(self, query, k=3):
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix)[0]
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k]
        return [{"source": self.chunks[i]["source"], "score": round(float(scores[i]), 4),
                 "text": self.chunks[i]["text"]} for i in order]

    def answer(self, question):
        hits = self.retrieve(question, k=3)
        context = "\n".join(f"[{h['source']}]\n{h['text']}" for h in hits)
        messages = [{"role": "system", "content": POLICY_SYSTEM},
                    {"role": "user", "content": f"CONTEXT:\n{context}\nQUESTION:\n{question}"}]
        reply = mock_llm.chat(messages).choices[0].message.content
        return reply, [h["source"] for h in hits]


_default = None


def retrieve(query, k=3):
    """Module-level retrieval over the default 40/10 chunks (shared with the refund agent)."""
    global _default
    if _default is None:
        _default = Retriever(chunk_documents())
    return _default.retrieve(query, k)


def answer(question):
    retrieve("")   # make sure the default index exists
    return _default.answer(question)


def evaluate(retriever, qa):
    rows = []
    for q in qa.itertuples(index=False):
        reply, sources = retriever.answer(q.question)
        answerable = q.expected_doc != "NONE"
        rows.append({"question": q.question, "expected_doc": q.expected_doc,
                     "doc_in_top3": (q.expected_doc in sources) if answerable else None,
                     "fact_in_answer": (q.expected_fact in reply) if answerable else None,
                     "fallback": reply.startswith("I could not find") if not answerable else None,
                     "answer": reply})
    return pd.DataFrame(rows)


def summary(ev):
    a, u = ev[ev["expected_doc"] != "NONE"], ev[ev["expected_doc"] == "NONE"]
    return (f"{int(a['doc_in_top3'].sum())}/{len(a)}", f"{int(a['fact_in_answer'].sum())}/{len(a)}",
            f"{int(u['fallback'].sum())}/{len(u)}")


if __name__ == "__main__":
    rep = Report("d1_rag")
    chunks = chunk_documents()
    counts = pd.Series([c["source"] for c in chunks]).value_counts()
    rep.add(f"**Chunking (40 words, overlap 10):** {len(chunks)} chunks -- "
            + ", ".join(f"{k} {v}" for k, v in counts.items()) + "\n")

    top = retrieve("refund policy late delivery")
    rep.table("retrieve('refund policy late delivery', k=3)",
              pd.DataFrame([(h["source"], h["score"], h["text"][:60] + "...") for h in top],
                           columns=["source", "score", "text (start)"]), floatfmt="{:.4f}")

    qa = pd.read_csv(os.path.join(RAW, "policy_eval.csv"), keep_default_na=False)
    ev10 = evaluate(_default, qa)
    ev0 = evaluate(Retriever(chunk_documents(overlap=0)), qa)
    rep.table("Policy evaluation (14 questions)", pd.DataFrame(
        [("40 words, overlap 10", *summary(ev10)), ("40 words, overlap 0", *summary(ev0))],
        columns=["chunking", "expected doc in top 3 (12 answerable)", "answer contains expected fact",
                 "fallback on 2 unanswerable"]))
    broken = ev0[(ev0["expected_doc"] != "NONE") & ~(ev0["doc_in_top3"].astype(bool) & ev0["fact_in_answer"].astype(bool))]
    rep.table("Questions that fail with overlap 0", broken[["question", "expected_doc", "doc_in_top3",
                                                             "fact_in_answer", "answer"]])
    rep.table("Answers with overlap 10", ev10[["question", "answer"]])
    rep.save()

    assert len(chunks) == 15 and counts.to_dict() == {"refund_policy.txt": 4, "delivery_policy.txt": 3,
                                                     "escalation_policy.txt": 3, "payment_policy.txt": 3,
                                                     "privacy_policy.txt": 2}
    assert all(h["source"] == "refund_policy.txt" for h in top)
    assert summary(ev10) == ("12/12", "12/12", "2/2") and len(broken) >= 1
