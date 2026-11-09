"""Shared paths, constants and a small report writer used by every step."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
CLEAN = os.path.join(ROOT, "data", "clean")
POLICIES = os.path.join(ROOT, "data", "policies")
DB_PATH = os.path.join(ROOT, "data", "instamart.db")
SQL_PATH = os.path.join(ROOT, "sql", "queries.sql")
OUTPUTS = os.path.join(ROOT, "outputs")
REPORTS = os.path.join(ROOT, "reports")
STATE = os.path.join(ROOT, "state")

# the supplied mock_llm.py lives at the repository root
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SEED = 42
SNAPSHOT = "2025-10-01 00:00:00"   # Part B RFM snapshot
CUTOFF = "2025-09-01"              # Part B lapse cutoff

for _d in (CLEAN, OUTPUTS, REPORTS, STATE):
    os.makedirs(_d, exist_ok=True)


def md_table(df, floatfmt="{:,.2f}"):
    """Render a DataFrame as a GitHub Markdown table (no extra dependency)."""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        cells = [floatfmt.format(v) if isinstance(v, float) else str(v).replace("\n", " ").replace("|", "\\|")
                 for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


class Report:
    """Collects Markdown for one step, echoes it to stdout and saves it to reports/<name>.md."""

    def __init__(self, name):
        self.path = os.path.join(REPORTS, f"{name}.md")
        self.parts = []

    def add(self, text=""):
        print(text)
        self.parts.append(text)

    def table(self, title, df, **kw):
        self.add(f"**{title}**\n\n{md_table(df, **kw)}\n")

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.parts) + "\n")
