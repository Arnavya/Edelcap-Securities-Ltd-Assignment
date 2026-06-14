# REPRODUCIBILITY — FinFlow Reasoning Engine

How to reproduce results from a clean clone, and what is vs isn't deterministic.

## From a clean clone (containerized — recommended)
```bash
git clone https://github.com/Arnavya/Edelcap-Securities-Ltd-Assignment && cd Edelcap-Securities-Ltd-Assignment
cp .env.example .env            # add GROQ_API_KEY (not needed for tests)
docker compose build
docker compose --profile tests run --rm tests     # 90 tests, offline, deterministic
docker compose up app                              # dashboard at http://localhost:8501
docker compose --profile eval run --rm eval        # evaluation (needs key + quota)
```

## From a clean clone (local)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
PYTHONPATH=. pytest
PYTHONPATH=. streamlit run dashboard/app.py
```

## Pinned environment
- Base image `python:3.11-slim`; dependencies pinned by lower bound in `requirements.txt`
  (`groq>=0.11`, `pydantic>=2`, `rank-bm25>=0.2.2`, `python-dotenv`, `streamlit`, `pandas`, `pytest`).
  Verified working set: groq 1.4.0, rank-bm25 0.2.2, streamlit 1.37.1, pandas 2.2.2, pydantic 2.8.2.
- For byte-stable rebuilds, pin exact versions (`pip freeze > requirements.lock`) — not done here to keep the intern scope light.

## What is deterministic (reproducible)
- **The full test suite (90 tests).** Uses the mock/scripted providers — no network, no clock, no randomness. Same result every run, host or container.
- **Retrieval (BM25).** Deterministic given the corpus; stable tie-breaks by `source_id`.
- **All deterministic metrics:** evidence overlap/recall, V1→V2 deltas, `newly_retrieved/cited`, the leakage gate, relevance scoring.
- **The dataset.** Versioned JSON; stable IDs.

## What is NOT deterministic (and why)
- **Live LLM outputs (Groq).** Investigation/gap/learning/judge calls vary run-to-run even at temperature 0 (provider-side nondeterminism). Therefore the **live evaluation numbers are not byte-reproducible**; expect small variation. Prompt versions and judge versions are recorded on every artifact so runs remain *interpretable*, not identical.
- **Quota-dependent completeness.** Groq free tier caps ~100k tokens/day per model; a full 70b evaluation may not complete in one sitting on the free tier.

## Reproducing the evaluation specifically
- `scripts/run_evaluation.py` pins prompt versions and records the model on the
  `EvaluationRun`. Re-running yields the same *structure* and *gate logic*; the
  scored values move within LLM variance.
- The directional validation (P2→H2) was run on `llama-3.1-8b-instant` due to the
  70b daily cap; the canonical 70b numbers are pending (see RESEARCH_FINDINGS.md).
  To reproduce canonically: set `FINFLOW_MODEL=llama-3.3-70b-versatile`, ensure
  sufficient quota, and run the `eval` mode.

## Reset state
```bash
docker compose down -v        # drops the finflow-db volume (all generated artifacts)
```
