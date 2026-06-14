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

# read-only dashboard
docker compose up app                                 # http://localhost:8501
# or: PYTHONPATH=. streamlit run dashboard/app.py

# interactive human-in-the-loop dashboard (ask → V1 → expert answer → V2)
docker run --rm -p 8501:8501 --env-file .env -v finflow-db:/data finflow-reasoning-engine live
# or: PYTHONPATH=. streamlit run dashboard/live_app.py
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
  persisted, diagnosable snapshots. **V2 applies an incident-only soft service-scope:**
  for `prod_incident` questions, expansion-only evidence from a service other than V1's
  top result is down-ranked (×0.30, not dropped); other families are unaffected.
- **Learning:** patterns split into *retrieval signals* and *reasoning heuristics*;
  a deterministic n-gram leakage gate guarantees no verbatim expert text is stored;
  relevance scoring gates which patterns transfer.
- **Evaluation:** versioned, fully-logged LLM judges plus deterministic evidence
  overlap and improvement. **Active similarity judge = `judge_similarity_v3`** (graded
  partial credit + "share of key claims" rubric); `v1`/`v2` prompts retained for
  provenance only. Rubric-based root-cause judge. Success signal = **rubric coverage +
  similarity** (blended), not raw source retrieval.
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

## Dashboards

### Read-only — `dashboard/app.py`
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

### Interactive (human-in-the-loop) — `dashboard/live_app.py`
`PYTHONPATH=. streamlit run dashboard/live_app.py` (or `… finflow-reasoning-engine live`),
default model `llama-3.1-8b-instant`: pick/type a question → **Run V1** → type the
expert answer → **Learn & generate V2** → V1/V2 comparison with calibrated metrics.
Writes to the same SQLite the read-only dashboard reads. Needs `GROQ_API_KEY`.

## Known Limitations
- Central research claim **not canonically validated** — the `llama-3.3-70b-versatile`
  evaluation is Groq-quota-blocked; all live numbers are **8B / single-sample / one
  human-proxy rater** (directional, not statistically robust; 3 twin families).
- **Service-scope filter is marginal at ×0.30** (~−1 contamination item on P2). The
  *family gate* (not the down-rank strength) prevents the P4 regression, so the penalty
  can be strengthened later with no P4 risk.
- **Base-matched cross-service contamination is unaddressed** — the filter only
  down-ranks *expansion-only* items; off-service evidence matching the question's own
  terms still surfaces.
- **Judge v3 mild over-generosity** on partially-wrong answers (e.g. ~0.58 vs human
  ~0.45) — far better than v2's collapse, tunable later.
- **Out-of-distribution questions can confabulate** — no abstention/low-confidence
  path; the tokenizer treats `deploy` ≠ `deployment`.
- `MockProvider` is a deterministic test harness, not a functional offline demo.
- Synthetic dataset is authored to *exhibit* the learning gap (see `TECHNICAL_DEBT.md`).
- Some historical docs (`FINAL_*`, parts of `PROJECT_STATUS.md`/`RESEARCH_FINDINGS.md`)
  describe the pre-v3/pre-filter state; **this README is the current source of truth.**

## Future work
- Run the canonical 70B post-P7.1 evaluation (dev-tier key or quota reset).
- Expand families/categories for statistical robustness.
- Add retry/backoff for transient API errors.
- Optional semantic retriever behind the existing `Retriever` interface.
- Tighten retrieval-signal specificity to raise evidence-utilization signal-to-noise.

## Research status
- ✅ **Mechanisms verified** (90 offline tests): leakage-free generalizable learning, retrieval transfer, evidence utilization, relevance gating, judge calibration, incident-only service-scope.
- ✅ **Judge calibration (v3) shipped** (`479db31`): similarity MAE vs human **0.55→0.10**; the P4 near-identical-answer case **0.00→0.90**.
- ✅ **Incident-only soft service-scope shipped** (`da21020`): **no P4 regression** (0.60→0.60), average v3 similarity non-regressing (0.596 ≥ 0.590), modest P2 contamination reduction.
- ✅ **Directional transfer positive** (`llama-3.1-8b-instant`, P2→H2): held-out blended **+0.325**, ablation **+0.125**, rubric **0.50→0.75**, leakage **PASS**.
- ⏳ **Canonical 70B evaluation: not completed** (quota); the earlier pre-tuning canonical run failed the gates and has not been re-measured on 70B.
- ➡️ **Conclusion: validated in mechanism + directionally; not yet canonically (70B) confirmed.**

## Documentation map
`PROJECT_STATUS.md` · `TECHNICAL_DEBT.md` · `RESEARCH_FINDINGS.md` · `REPO_TREE.md` ·
`RELEASE_READINESS.md` · `DOCKER_GUIDE.md` · `REPRODUCIBILITY.md` · `data/DATASET_DESIGN.md`
· `FINAL_ONE_PAGER.md` · `DEMO_SCRIPT.md` · `FINAL_PROJECT_SUMMARY.md`
