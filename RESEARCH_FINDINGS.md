# RESEARCH_FINDINGS — FinFlow Reasoning Engine

> **Post-release update (origin/main @ da21020):** findings below predate the judge
> recalibration and the retrieval filter. Since then: **judge_similarity_v3** is the active
> similarity judge (MAE vs human 0.55→0.10; P4 0.00→0.90), and an **incident-only soft
> service-scope** on V2 retrieval shipped (no P4 regression; avg v3 similarity non-regressing).
> The canonical 70B confirmation is still pending (quota). See `README.md` for current state.

All measured results to date, classified **VERIFIED** (deterministic / reproducible),
**DIRECTIONAL** (single non-canonical live run), or **UNVERIFIED** (not yet measured).
**Central claim:** the system learns generalizable, leakage-free investigative methods
that improve held-out reasoning quality (not just retrieval).

---

## VERIFIED (deterministic, 83 offline tests, zero API calls)
- **Leakage-free learning (mechanism).** The sanitization gate drops any learning-pattern field sharing a ≥5-gram with the expert answer; the learning schema has no answer field. Asserted by `test_no_verbatim_leak`-style tests and `test_learning`. *Status: VERIFIED.*
- **Retrieval transfer (mechanism).** Learned generic signals + commit routing surface a previously-missed commit on a held-out twin: H2 V1 excludes `commit:a4`; H2 V2 includes it (`test_h2_transfer_from_p2`). Same for P2 `commit:a1`. *Status: VERIFIED (mechanism), deterministic.*
- **V2 consumes new evidence.** `evidence_utilization` > 0 when V2 cites newly-retrieved evidence (`test_evidence_utilization_recorded`). *Status: VERIFIED.*
- **Relevance filtering.** Service-specific patterns are rejected for an off-service twin; general patterns transfer; diagnostics recorded (`test_memory_rejects_irrelevant_patterns_with_diagnostics`). *Status: VERIFIED.*
- **Gate + persistence plumbing.** Four gates computed, `EvaluationRun` persisted, every judge call logged (`test_evaluation`). *Status: VERIFIED.*
- **Citation validation, confidence clamping, deterministic retrieval/metrics.** *Status: VERIFIED.*

## DIRECTIONAL (one live run, `llama-3.1-8b-instant`, single family P2→H2)
Run after P7.1 tuning, on a non-canonical (weaker) model, because the 70b quota was exhausted.

| H2 metric | V1 | V2 | ablation |
|---|---|---|---|
| similarity | 0.40 | 0.80 | 0.80 |
| rubric coverage | 0.50 | 0.75 | 0.50 |
| evidence recall | 0.20 | 0.40 | 0.60 |
| **blended (sim+rubric)** | 0.45 | **0.78** | 0.65 |
| evidence_utilization | 0.00 | 0.17 | — |

- **Held-out improvement (H2): +0.325 blended** (target > 0.10). *DIRECTIONAL.*
- **Ablation delta (H2): +0.125** (target > 0.10). *DIRECTIONAL.*
- **Leakage: PASS** (0 redactions of kept patterns, max overlap 0.00). *DIRECTIONAL live + VERIFIED deterministically.*
- **Qualitative:** newly-retrieved `commit:a4` was referenced in V2 reasoning and the V2 answer correctly named "a recent consumer refactor that dropped the deduplication step" (rubric RC2) — V1 had not. The transferred reasoning heuristic was generic ("inspect recent commits for removed safeguards").
- **Caveats:** 8b model ≠ canonical 70b; n=1 family; small absolute utilization (denominator includes cross-domain noise).

## UNVERIFIED (not measured / failed to complete)
- **Canonical central claim (70b, H1–H3).** Not measured. The full `run_evaluation.py` on `llama-3.3-70b-versatile` could not complete — Groq free-tier daily token cap (100k/day) exhausted. *Status: UNVERIFIED — this is the headline gap.*
- **Same-question improvement (post-tuning, 70b).** Unverified.

### The one completed canonical run (P7, PRE-tuning, judge v1) — FAILED gates
This ran before P7.1 and with the lenient judge v1; recorded honestly:

| gate | value | threshold | result |
|---|---|---|---|
| held_out_generalization | 0.021 | 0.10 | ❌ FAIL |
| ablation_attribution | 0.013 | 0.10 | ❌ FAIL |
| same_question_improvement | −0.151 | 0.20 | ❌ FAIL |
| leakage_free_learning | 0.0 | 0.0 | ✅ PASS |

Root cause of that failure (analyzed in P7): retrieval improved but reasoning didn't follow; lenient judge gave V1 ~0.80 (no headroom); guidance sometimes regressed V2. P7.1 targeted exactly these and the directional 8b run shows the fix works *on 8b* — but **this has not been reconfirmed on 70b**, so the pre-tuning FAIL has not been formally superseded by a passing canonical run.

---

## Honest one-line summary
The **mechanisms** (leakage-free generalizable learning, retrieval transfer, evidence utilization) are **VERIFIED**. The **quantitative central claim** is **DIRECTIONALLY supported on 8b for one family** and **UNVERIFIED on the canonical 70b model / full held-out set**. The only completed canonical run (pre-tuning) **failed** the quality gates except leakage. **No success on the central claim should be declared until a canonical 70b run passes.**
