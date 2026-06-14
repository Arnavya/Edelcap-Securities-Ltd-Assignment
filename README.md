# FinFlow — Expert-Learning Organizational Reasoning Engine

Intern project **INT-AI-01**. A small but functional reasoning engine that answers
organizational questions about a synthetic fintech org (**FinFlow**) by investigating
knowledge sources (Slack, issue tickets, wiki, git commits), drafts a **V1** answer
with a cited reasoning trace, learns from a human expert's ground-truth answer by
distilling **generalizable, leakage-free investigative patterns**, and produces a
**V2** answer — aiming to demonstrate learned *reasoning*, not memorized answers.

> **Research status (honest):** the learning *mechanisms* are verified by tests, and
> a *directional* validation on `llama-3.1-8b-instant` shows positive held-out
> transfer. The **canonical `llama-3.3-70b-versatile` post-tuning evaluation has not
> completed** (Groq quota), so the central claim is **not yet canonically validated**.
> See [Research status](#research-status) and `RESEARCH_FINDINGS.md`.

---

## Installation

### Docker (recommended)
```bash
git clone <repo> && cd finflow-reasoning-engine
cp .env.example .env          # set GROQ_API_KEY (not needed for tests)
docker compose build
```

### Local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
Requires Python 3.11+. Verified deps: groq 1.4.0, rank-bm25 0.2.2, streamlit 1.37.1,
pandas 2.2.2, pydantic 2.8.2.

## Quickstart
```bash
# offline test suite (no API key)
docker compose --profile tests run --rm tests        # or: PYTHONPATH=. pytest

# one live investigation (needs GROQ_API_KEY)
PYTHONPATH=. python scripts/seed_db.py
PYTHONPATH=. python scripts/run_pipeline.py --question P2

# dashboard
docker compose up app                                 # http://localhost:8501
# or: PYTHONPATH=. streamlit run dashboard/app.py
```

## Architecture
Plain linear pipeline — no workflow/stage frameworks:
```
Question
  → Retrieval (BM25 + per-source balancing; learned expansion/routing in V2)
  → Investigation Agent (V1: answer + cited reasoning trace)
  → Human Answer (ground truth)
  → Gap Analysis (deterministic evidence diff + LLM reasoning/rubric gaps)
  → Learning Event Generator (generalizable patterns; leakage gate drops verbatim)
  → Learning Memory (answer-free; relevance-filtered injection)
  → Investigation Agent (V2: memory-augmented; revises reasoning around new evidence)
  → Evaluation (LLM judges + deterministic metrics + four gates)
```
- **LLM:** pluggable `LLMProvider`; implemented = `GroqProvider` (default
  `llama-3.3-70b-versatile`) and `MockProvider` (offline tests). Only `finflow/llm/`
  imports a vendor SDK.
- **Retrieval:** `Retriever` interface + `BM25Retriever` (deterministic; swappable;
  no FAISS). Per-source top-k balancing; soft routing bias; pluggable expansion;
  persisted, diagnosable snapshots.
- **Learning:** patterns split into *retrieval signals* and *reasoning heuristics*;
  a deterministic n-gram leakage gate guarantees no verbatim expert text is stored;
  relevance scoring gates which patterns transfer.
- **Evaluation:** versioned, fully-logged LLM judges (similarity + rubric root-cause)
  plus deterministic evidence overlap and improvement. Success signal = **rubric
  coverage + similarity** (blended), not raw source retrieval.
- **Persistence:** SQLite (9 tables); the dashboard is strictly read-only over it.

## Evaluation workflow
```bash
# full canonical evaluation across the three twin families (needs key + quota)
docker compose --profile eval run --rm eval
# or: rm -f finflow.db && PYTHONPATH=. python scripts/run_evaluation.py
```
Per twin family it runs: train learning cycle (V1→V2 on the train question),
held-out transfer (baseline V1 vs post-learning V2 on the twin), and an ablation
(V2 with learning stripped). It computes four gates and persists an `EvaluationRun`.
> The canonical 70B run is currently **quota-blocked**; see Research status.

## Dashboard walkthrough
`streamlit run dashboard/app.py` → single page, read-only:
1. **Question Feed** — all questions (family, held-out flag, run count).
2. **Retrieved Evidence** — V1 vs V2 table flagging *newly retrieved* / *newly cited*; inspectable retrieval traces (scores, `from_expansion`, matched terms, diagnostics).
3. **V1 Answer** + reasoning steps.
4. **Expert Answer** (ground truth).
5. **Gap Analysis** — severity, missed/extra evidence, missed root causes.
6. **Learning Event** — patterns by type + leakage metrics ("generalized hints only").
7. **V2 Answer** + reasoning steps + logged judge results.
8. **Metrics & Gates** — central-claim/verdict, per-question scorecard, transfer metrics.
9. **Learning Trend** — V1 vs V2 blended bar chart.

## Limitations
- Central research claim **not canonically validated** (Groq free-tier daily token cap blocks the full 70B run).
- `MockProvider` is for deterministic tests, not a functional offline demo (it returns hash strings, not real answers).
- Small sample (3 twin families) → illustrative, not statistically robust.
- Synthetic dataset is authored to *exhibit* the learning gap (see `TECHNICAL_DEBT.md`).
- LLM judge variance; live numbers are not byte-reproducible.

## Future work
- Run the canonical 70B post-P7.1 evaluation (dev-tier key or quota reset).
- Expand families/categories for statistical robustness.
- Add retry/backoff for transient API errors.
- Optional semantic retriever behind the existing `Retriever` interface.
- Tighten retrieval-signal specificity to raise evidence-utilization signal-to-noise.

## Research status
- ✅ **Mechanisms verified** (83 offline tests): leakage-free generalizable learning, retrieval transfer, evidence utilization, relevance gating.
- ✅ **Directional transfer positive** (`llama-3.1-8b-instant`, P2→H2): held-out blended **+0.325**, ablation **+0.125**, rubric **0.50→0.75**, leakage **PASS**.
- ⏳ **Canonical 70B post-P7.1 evaluation: not completed** (quota). The only completed *canonical* run was **pre-P7.1** and failed the quality gates (generalization 0.021, ablation 0.013, same-question −0.151; leakage PASS).
- ➡️ **Conclusion: the central claim is not yet canonically validated.** Promising mechanism + directional evidence; awaiting the canonical measurement.

## Documentation map
`PROJECT_STATUS.md` · `TECHNICAL_DEBT.md` · `RESEARCH_FINDINGS.md` · `REPO_TREE.md` ·
`RELEASE_READINESS.md` · `DOCKER_GUIDE.md` · `REPRODUCIBILITY.md` · `data/DATASET_DESIGN.md`
· `FINAL_ONE_PAGER.md` · `DEMO_SCRIPT.md` · `FINAL_PROJECT_SUMMARY.md`
