# TECHNICAL_DEBT — FinFlow Reasoning Engine

Every shortcut, workaround, prompt/dataset tweak, and known weakness. Items that
affect **evaluation validity** are marked ⚠️.

## Dataset tweaks (authored to exhibit the learning gap)
- ⚠️ **`ticket:PAY-540` reworded** (P5). Originally stated the disabled-idempotency mechanism explicitly, which let V1 get P2's root cause "for free" from the fix ticket. Reworded so the mechanism lives only in `commit:a1`/`a15`. *Validity impact:* the V1→V2 root-cause gain depends on this; without it, V1 already scores high. Legitimate (keeps causal links implicit per design) but it is the dataset being shaped to produce the intended gap.
- ⚠️ **`commit:a4` body + file path reworded** (P6). Removed "notification" from prose and the `Files:` path so the H2 query can't lexically retrieve it in V1. *Validity impact:* the H2 transfer demonstration requires a4 to be missed by V1; this tweak guarantees it. Same class as PAY-540.
- **General:** the corpus is intentionally constructed so each question has a "missed" piece of evidence reachable only via learned expansion. This is by design (synthetic dataset), but means the success story is partly a property of the authored data, not an independent result. External validity is limited to "the mechanism works on data shaped to need it."

## Prompt tweaks / versions
- **`investigation_v2`** (P7.1) added to force V2 to *revise* reasoning around newly-surfaced evidence. The V1↔V2 difference is now both retrieval AND a different prompt — intended, but it means "V2" is not a pure re-run of V1 with extra context.
- ⚠️ **`judge_similarity_v2`** (P7.1) is stricter than v1. *Validity impact:* the only **completed** canonical run (P7, pre-tuning) used judge v1, so its numbers are not directly comparable to any post-tuning numbers. A clean before/after must hold the judge version constant.
- **`learning_extract_v2`** (P7.1) asks for separated retrieval-signals vs reasoning-heuristics. Output quality depends on the LLM following this; not guaranteed on weaker models.

## Evaluation design caveats ⚠️
- **LLM-as-judge variance.** Similarity/root-cause are model-scored. Root-cause uses a fixed rubric (good), but similarity remains subjective. Scores are logged + versioned but still noisy.
- **`evidence_utilization` counts noise in the denominator.** Generic retrieval signals surface cross-domain evidence (e.g. payment commits during a notification incident) that the model correctly ignores; these inflate the denominator, so the metric *understates* true utilization (observed 0.17 on H2 where the one relevant new item was used).
- **Gate thresholds (0.10 / 0.10 / 0.20) and relevance threshold (0.65) are heuristic.** Not derived; chosen as reasonable targets. Not tuned to manufacture success, but not independently justified either.
- **n=3 twin families.** Aggregated gate values are means over a tiny sample.
- **Ablation ≈ baseline.** Ablation runs the V2 path with empty context, which is close to the V1 baseline; the ablation gate and the generalization gate are therefore correlated, not fully independent signals.

## Provider / runtime shortcuts
- **MockProvider returns hash strings, not JSON.** Full offline runs need *scripted* providers (tests supply these). `FINFLOW_PROVIDER=mock` is not a working demo, only a plumbing/test harness. Documented limitation.
- **Scripts require `PYTHONPATH=.`** (no `pip install -e`). To be fixed by P9 Docker (WORKDIR/PYTHONPATH).
- **Groq free-tier quota** exhausted by a day's runs (100k tokens/day, per model). Canonical eval not runnable without a higher tier, a fresh key, or staged runs. Directional validation was done on `llama-3.1-8b-instant` (separate per-model quota).
- **Global env dependency conflicts** (tensorflow/thinc/protobuf/numpy) surfaced during `pip install` into the anaconda base environment. Not project dependencies; Docker will isolate.

## Minor / cosmetic
- Relevance diagnostics are persisted into `RetrievalSnapshot.diagnostics.notes` (string list) rather than a dedicated field, to avoid changing the persistence schema mid-build.
- `LearnedContext` is a transient dataclass (not persisted); its applied/rejected diagnostics survive only via the snapshot notes.
- No retry/backoff on Groq calls — a transient 429/5xx aborts a run (seen with the rate limit).
- `list_judge_results` exists on `SQLiteRepository` but not on the `Repository` ABC (dashboard uses the concrete type).

## Not debt (by design, noted to avoid confusion)
- Single hosted provider (Groq) + Mock only — Anthropic/OpenAI/Ollama intentionally not implemented.
- BM25 over embeddings — deliberate (determinism, Docker simplicity); `Retriever` keeps semantic swap-in open.
