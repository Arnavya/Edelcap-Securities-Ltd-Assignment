# RELEASE_READINESS — FinFlow Reasoning Engine

> **Current state (origin/main):** `judge_similarity_v3` (calibrated similarity judge), an **incident-only soft service-scope** on V2 retrieval, and the **interactive HITL dashboard** (`dashboard/live_app.py`) are shipped; the suite is **90 tests**. This file is a historical snapshot — see `README.md` for current truth.

Release-candidate audit verdict. **Audit only — no code changed.**

## 1. Is the architecture complete?
**Yes for the engine (P0–P8); deployment packaging (P9–P10) remains.**

All designed components exist, are wired end-to-end, and are covered by 83 passing
offline tests:
- pluggable LLM (Groq default + Mock), `Retriever`/`BM25Retriever`, knowledge store
- investigation (V1/V2), gap analysis, learning-event generation + leakage gate, learning memory
- hybrid evaluation (versioned logged judges + deterministic metrics) with four explicit gates
- first-class SQLite persistence (9 tables) and a strictly read-only dashboard

Not done: **P9 Dockerization**, **P10 one-pager/demo polish**. These are packaging
and presentation, not core architecture.

**Architecture completeness: ~90% (engine complete; deployment/polish pending).**

## 2. Is the research claim verified?
**No — not canonically. The mechanisms are verified; the quantitative central claim
is only directionally supported and remains unverified on the canonical model.**

- Mechanisms (leakage-free generalizable learning, retrieval transfer, evidence
  utilization, relevance gating): **VERIFIED** by deterministic tests.
- Central claim "learning improves held-out reasoning quality": **DIRECTIONAL** —
  one live run on `llama-3.1-8b-instant`, one family (P2→H2): held-out blended
  +0.325, ablation +0.125, leakage PASS, rubric 0.50→0.75.
- Canonical claim (`llama-3.3-70b-versatile`, H1–H3): **UNVERIFIED** (Groq quota).
- The only **completed** canonical run (pre-tuning, judge v1) **failed** the quality
  gates (generalization 0.021, ablation 0.013, same-question −0.151; leakage PASS).
  It has not yet been superseded by a passing canonical run.

**Research-claim verification: NOT MET. Do not declare success.**

## 3. What evidence supports these answers?
**For "architecture complete":**
- 90/90 tests passing, fully offline; 42 source files; all phase exit criteria met (PROJECT_STATUS.md).
- Live V1 + gap (70b) and live learning cycle + H2 transfer (8b) executed end-to-end.
- Dashboard boots headless: HTTP 200, no tracebacks.

**For "research claim not verified":**
- Directional 8b run only (RESEARCH_FINDINGS.md): non-canonical model, n=1 family.
- Canonical 70b full eval never completed (rate-limit traceback).
- Pre-tuning canonical run failed gates; judge version changed since, so even that
  isn't a clean baseline (TECHNICAL_DEBT.md ⚠️).

## Recommendation
**Proceed to P9 (Dockerization) now; defer P10's results/one-pager until a canonical
70b evaluation is run. Do not declare the research claim met until then.**

Rationale:
- P9 is **independent of the research outcome**, reduces environment risk (isolates
  the global dependency conflicts), removes the `PYTHONPATH`/quota friction, and is in
  fact the cleanest way to *run the canonical evaluation reproducibly* (clone → add
  key → `docker compose up` / `--profile eval`).
- P10 can do its structural parts (README, demo script) but the **one-pager's results
  section must wait** for canonical numbers, or it would overstate findings.
- The blocker to verification is **quota, not engineering**: obtain a Groq dev-tier
  key (or wait for the daily reset and run staged per-family) and execute the full
  `run_evaluation.py` on 70b before any release/success statement.

**Bottom line: build-complete and demonstrably working in mechanism; research result
is promising but not canonically proven. Ship the packaging (P9), hold the claim.**
