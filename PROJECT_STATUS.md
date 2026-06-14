# PROJECT_STATUS — FinFlow Expert-Learning Organizational Reasoning Engine

Release-candidate audit. Status as of P8 completion. **Audit only — no code changed.**

## Phase status (P0–P8)

| Phase | Title | Status | Completed | Remaining |
|---|---|---|---|---|
| P0 | Skeleton & contracts | ✅ Done | pydantic models, `config`, repo layout, 8 model tests | — |
| P1 | LLM abstraction + Mock + Groq | ✅ Done | `LLMProvider`, `GroqProvider` (default), `MockProvider`, factory; SDK isolated; live call verified | — |
| P2 | Dataset authoring | ✅ Done | 54 evidence items (14 slack/14 ticket/8 wiki/18 commit), 6 primary + 3 held-out questions, rubrics + gold sets, implicit causal links | — |
| P3 | Retrieval | ✅ Done | `Retriever` interface + `BM25Retriever`, per-source balancing, pluggable expansion, routing bias, diagnostics, persisted snapshots | semantic retriever (deferred by design) |
| P4 | End-to-end V1 + persistence | ✅ Done | `InvestigationAgent` (validated citations, confidence), `Orchestrator`, SQLite repo, live V1 verified | — |
| P5 | Gap analysis | ✅ Done | `GapAnalysisAgent`, deterministic evidence diff + severity, LLM reasoning/rubric gaps | — |
| P6 | Learning loop + V2 | ✅ Done | `LearningEventGenerator`, leakage gate, `LearningMemory`, V2 (memory-augmented), H2 transfer; `newly_retrieved/cited` | — |
| P7 | Hybrid evaluation + gates | ✅ Built | versioned judges (logged), deterministic overlap/improvement, 4 explicit gates, `EvaluationRun` persisted | canonical 70b measurement (blocked by quota) |
| P7.1 | Learning quality tuning | ✅ Built | V2 "revise" prompt, retrieval/reasoning pattern split, relevance filtering, `evidence_utilization`, stricter judge | canonical 70b re-measurement |
| P8 | Dashboard | ✅ Done | read-only `dashboard/data.py` + `dashboard/app.py`, boots clean (HTTP 200) | — |

## Remaining work
- **P9 — Dockerization** (Dockerfile, docker-compose, entrypoint, `.env` strategy). Not started.
- **P10 — README / one-pager / demo polish**. Partial (README has quickstart); one-pager + ≤3-min demo not done.
- **Canonical evaluation** — full `run_evaluation.py` on `llama-3.3-70b-versatile` across H1–H3. **Not completed** (Groq free-tier daily token cap).

## Repository inventory
- Source: **42 Python files** in `finflow/` (~2,620 LOC); **8 prompt templates**; **3 scripts**; **2 dashboard modules** (~377 LOC).
- Tests: **9 files, 83 tests** (all passing, fully offline via mock/scripted providers, zero API calls).
  - models 8 · llm 11 · dataset 12 · retrieval 14 · investigation 8 · gap 5 · learning 9 · evaluation 9 · dashboard 7
- Data: 54 evidence items + 9 questions + 9 human answers (with rubrics + gold evidence).
- Persistence tables: questions, human_answers, answers, retrieval_snapshots, gap_analyses, learning_events, judge_results, evaluation_runs, runs.

## Known limitations
1. **Central research claim not canonically verified** — only directionally (8b model, one family). See RESEARCH_FINDINGS.md.
2. **MockProvider is for tests, not a functional offline demo** — it returns deterministic hash strings, not real answers. `FINFLOW_PROVIDER=mock` exercises the plumbing but does not produce meaningful investigations; a real demo needs a Groq key.
3. **Small sample** — 3 twin families; metrics are illustrative, not statistically robust (the brief acknowledges this).
4. **Dataset is authored to exhibit the learning gap** — synthetic by design (in scope), but specific lexical tweaks (PAY-540, commit:a4) keep the "missed" evidence out of the question's lexical reach. See TECHNICAL_DEBT.md.
5. **Scripts require `PYTHONPATH=.`** (no editable install). P9 Docker will normalize this.

## Open risks
- **R1 (high):** canonical 70b eval may not clear gates even post-tuning; current positive evidence is 8b-only. Mitigation: run canonical eval (dev-tier key or quota reset) before any success declaration.
- **R2 (medium):** Groq free-tier quota blocks full evaluation; reproducing the headline numbers needs a higher tier or staged runs.
- **R3 (medium):** LLM nondeterminism — V2 regressed on some questions in the (pre-tuning) canonical P7 run; not yet re-checked on 70b post-tuning.
- **R4 (low):** judge-prompt change (v1→v2) means the one completed canonical run (P7, judge v1) is not directly comparable to post-tuning numbers.
- **R5 (low):** global env dependency conflicts (tensorflow/thinc/protobuf) from pip installs into the anaconda base — unrelated to project deps but present; Docker isolates this.
