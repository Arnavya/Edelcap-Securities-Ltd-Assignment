# FinFlow — Expert-Learning Organizational Reasoning Engine (One-Pager)

> **Current state (origin/main):** `judge_similarity_v3` (calibrated similarity judge), an **incident-only soft service-scope** on V2 retrieval, and the **interactive HITL dashboard** (`dashboard/live_app.py`) are shipped; the suite is **90 tests**. This file is a historical snapshot — see `README.md` for current truth.

**Project:** INT-AI-01 · **Domain:** AI / Knowledge Management / Engineering Productivity

## Problem
Organizations scatter critical knowledge across Slack, issue trackers, wikis, and
code. AI assistants retrieve facts but miss the *causal reasoning* a senior engineer
applies — so their answers disagree with experts, and expertise stays trapped in
individuals. The goal: an AI that **learns how experts reason**, not one that searches
harder.

## Approach
A human-in-the-loop learning loop over a synthetic fintech org (FinFlow):
investigate → draft **V1** with cited reasoning → capture the **expert answer** →
**gap analysis** → distill **generalizable, leakage-free patterns** → re-investigate
as **V2**. The headline test is **generalization to a held-out twin question** the
system never received feedback on — proving learned *method*, not memorized answers.

## Architecture
Plain linear pipeline (no frameworks): BM25 retrieval (per-source balanced, learned
expansion/routing in V2) → Investigation Agent (V1/V2) → Gap Analysis → Learning Event
Generator (+ deterministic n-gram leakage gate) → Learning Memory (answer-free,
relevance-filtered) → V2 investigation → Evaluation (versioned LLM judges + deterministic
metrics + four gates). Pluggable LLM (Groq default + Mock); SQLite persistence; strictly
read-only Streamlit dashboard. Fully dockerized.

## Results (honest — no fabrication)
- **Verified (90 offline tests, deterministic):** leakage-free generalizable learning;
  retrieval transfer (held-out V2 surfaces a previously-missed commit V1 missed);
  evidence utilization; relevance gating; gate + persistence logic.
- **Directional (`llama-3.1-8b-instant`, P2→H2, one family):** held-out blended
  **+0.325**, ablation **+0.125**, rubric coverage **0.50→0.75**, similarity 0.40→0.80,
  leakage **PASS**; the newly-retrieved root-cause commit was referenced in V2 reasoning.
- **Canonical (`llama-3.3-70b-versatile`, all families): NOT COMPLETED** — blocked by
  Groq free-tier daily token quota. The only *completed* canonical run was **pre-tuning**
  and **failed** the quality gates (generalization 0.021, ablation 0.013, same-question
  −0.151; leakage PASS).
- **Central claim status: NOT YET CANONICALLY VALIDATED.** Mechanism + directional
  evidence are positive; the canonical measurement is pending.

## Limitations
Canonical evaluation quota-blocked; small sample (3 twin families); synthetic dataset
authored to exhibit the learning gap; LLM-judge variance (live runs not byte-reproducible);
`MockProvider` is a test harness, not a functional offline demo.

## Future work
Run the canonical 70B post-tuning evaluation (dev-tier key/quota reset); expand
families for statistical power; retry/backoff for API limits; optional semantic
retriever behind the existing interface; sharpen retrieval-signal specificity.

## Status
P0–P10 complete. 42 source files, **90 tests passing**, 54 evidence items, 9 questions,
Docker verified (611 MB image), dashboard verified (HTTP 200). Engine build-complete;
research claim awaiting one canonical run.
