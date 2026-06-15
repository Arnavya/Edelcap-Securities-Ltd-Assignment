# FinFlow — Expert-Learning Organizational Reasoning Engine

Project INT-AI-01. A reasoning engine that answers organizational questions over a
synthetic fintech knowledge base (Slack threads, tickets, wiki, commits). It drafts a
first answer (V1) with a cited reasoning trace, learns generalizable and leakage-free
investigative patterns from a human expert's answer, and produces an improved second
answer (V2). The aim is to demonstrate learned reasoning, not memorized answers.

## Documentation

- **`FinFlow_One-Pager.pdf`** — architecture, assumptions, results, and what to build next.
- **`FinFlow_Documentation.pdf`** — full report: architecture, design decisions, dataset,
  learning mechanism, evaluation, results, limitations.

## Setup

### Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set GROQ_API_KEY (not needed for the test suite)
```

Requires Python 3.11 or later. Verified dependencies: groq 1.4.0, rank-bm25 0.2.2,
streamlit 1.37.1, pandas 2.2.2, pydantic 2.8.2.

### Docker

```bash
cp .env.example .env            # set GROQ_API_KEY
docker compose build
```

## Running

```bash
# offline test suite (no API key needed)
PYTHONPATH=. pytest                                   # 90 tests
# or: docker compose --profile tests run --rm tests

# seed the knowledge base, then run one investigation (needs GROQ_API_KEY)
PYTHONPATH=. python scripts/seed_db.py
PYTHONPATH=. python scripts/run_pipeline.py --question P2

# dashboards
PYTHONPATH=. streamlit run dashboard/app.py           # read-only view of persisted runs
PYTHONPATH=. streamlit run dashboard/live_app.py      # interactive: ask -> V1 -> expert -> V2
# or: docker compose up app                            # http://localhost:8501

# full evaluation across the held-out families (needs key + quota)
PYTHONPATH=. python scripts/run_evaluation.py
# or: docker compose --profile eval run --rm eval
```

Key environment variables: `FINFLOW_PROVIDER` (groq or mock, default groq), `GROQ_API_KEY`,
`FINFLOW_MODEL` (default llama-3.3-70b-versatile), `FINFLOW_DB`, `FINFLOW_RETRIEVAL_K`
(default 4), `PORT` (default 8501).

## Project layout

```
finflow/      engine: llm, retrieval, agents, memory, evaluation, persistence, prompts
data/         synthetic corpus (feed, human answers, sources) — 54 items, 9 questions
dashboard/    read-only and interactive Streamlit apps
scripts/      seed_db, run_pipeline, run_evaluation
tests/        90 offline deterministic tests
```

## Status

The learning mechanisms are verified by the offline test suite, and a directional
validation on `llama-3.1-8b-instant` shows positive held-out transfer. The canonical
`llama-3.3-70b-versatile` evaluation is pending on API quota, so the central quantitative
claim is not yet canonically validated. See the PDFs for the full, honest breakdown.
