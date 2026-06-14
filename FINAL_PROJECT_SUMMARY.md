# FINAL_PROJECT_SUMMARY — FinFlow Reasoning Engine

> **Current state (origin/main):** `judge_similarity_v3` (calibrated similarity judge), an **incident-only soft service-scope** on V2 retrieval, and the **interactive HITL dashboard** (`dashboard/live_app.py`) are shipped; the suite is **90 tests**. This file is a historical snapshot — see `README.md` for current truth.

End-of-project inventory and research status. **Documentation only — no results fabricated.**

## Phases completed
| Phase | Title | Status |
|---|---|---|
| P0 | Skeleton & contracts | ✅ |
| P1 | LLM abstraction (Groq + Mock) | ✅ |
| P2 | Dataset authoring (54 items) | ✅ |
| P3 | Retrieval (BM25, balanced, expansion, diagnostics) | ✅ |
| P4 | End-to-end V1 + persistence | ✅ |
| P5 | Gap analysis | ✅ |
| P6 | Learning loop + V2 (leakage gate, memory, transfer) | ✅ |
| P7 | Hybrid evaluation + four gates | ✅ (built) |
| P7.1 | Learning-quality tuning | ✅ (built; directional validation positive) |
| P8 | Read-only dashboard | ✅ (verified) |
| P9 | Dockerization | ✅ (verified) |
| P10 | README / one-pager / demo / summary | ✅ (this) |
| — | Canonical 70B post-P7.1 evaluation | ⏳ **pending (quota-blocked)** |

## File counts
- **42** Python source files in `finflow/`
- **9** prompt templates (`investigation_v1/v2`, `gap_v1`, `learning_extract_v1/v2`, `judge_similarity_v1/v2/v3`, `judge_root_cause_v1`)
- **3** scripts (`seed_db`, `run_pipeline`, `run_evaluation`)
- **5** dashboard modules (`data.py` + read-only `app.py` + interactive `live_app.py` + shared `ui.py` + `__init__`)
- **10** test files

## Test counts
- **90 tests, all passing**, fully offline (mock/scripted providers; zero API calls).
- By area: models 8 · llm 11 · dataset 12 · retrieval 18 · investigation 8 · gap 5 · learning 9 · evaluation 9 · dashboard 7 · interactive 3.
- Verified passing both locally and **inside the container** (`docker run … tests` and `docker compose --profile tests run`).

## Dataset counts
- **54 evidence items**: 14 Slack · 14 tickets · 8 wiki · 18 commits (incl. 7 distractors).
- **9 questions**: 6 primary (P1–P6) + 3 held-out twins (H1–H3).
- **9 human answers** with per-question root-cause rubrics + gold evidence sets.

## Docker status
- ✅ Verified: clean build **611 MB**, **~42 s** (no cache).
- Multi-mode single image: `dashboard` (default, healthchecked) / `eval` / `tests` / `pipeline` / `seed`.
- Tests pass in-container; dashboard serves with **health HTTP 200**; secrets via `.env` only (none baked).

## Dashboard status
- ✅ Verified: boots headless, health endpoint 200, no runtime errors.
- Strictly read-only over SQLite; 9 sections incl. V1-vs-V2 evidence, newly retrieved/cited, evidence utilization, rubric coverage, leakage metrics, transfer metrics, gates, trend chart.

---

## Research status (explicit, per requirement)
- ✅ **Mechanisms are verified.** Leakage-free generalizable learning, retrieval transfer, evidence utilization, and relevance gating are all confirmed by the deterministic test suite (90 tests).
- ✅ **Directional transfer evidence is positive.** On `llama-3.1-8b-instant` (P2→H2, one family): held-out blended **+0.325**, ablation **+0.125**, rubric coverage **0.50→0.75**, similarity 0.40→0.80, leakage **PASS**; the newly-retrieved root-cause commit was referenced in V2 reasoning.
- ⏳ **Canonical post-P7.1 evaluation has not completed.** The full `llama-3.3-70b-versatile` run across all families is blocked by Groq's free-tier daily token quota; no canonical post-tuning numbers exist. The only completed *canonical* run was **pre-P7.1** and failed three of four gates (generalization 0.021, ablation 0.013, same-question −0.151; leakage PASS).
- ➡️ **The central claim is therefore NOT yet canonically validated.** It is supported by verified mechanisms and positive directional evidence, but awaits one quota-unblocked canonical evaluation to confirm or refute on the target model.

## To finish verification (no code changes needed)
Unblock Groq quota (dev-tier key or daily reset), then run the unchanged command:
```bash
docker compose --profile eval run --rm eval
# or: rm -f finflow.db && PYTHONPATH=. python scripts/run_evaluation.py
```
This produces the full score table, the four gates, and a persisted `EvaluationRun`.
