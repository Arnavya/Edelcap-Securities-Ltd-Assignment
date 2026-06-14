"""Full evaluation: measure the central claim — held-out improvement + leakage-free
learning — across the three twin families, with four explicit gates.

Usage:
    python scripts/run_evaluation.py
    FINFLOW_PROVIDER=mock python scripts/run_evaluation.py   # offline (needs scripted scores)
"""

from __future__ import annotations

from finflow.config import load_settings
from finflow.evaluation.evaluator import Evaluator
from finflow.evaluation.judge import Judge
from finflow.llm import GroqProvider, MockProvider
from finflow.orchestrator import Orchestrator
from finflow.retrieval import load_human_answers, load_questions

TWINS = [("P1", "H1"), ("P2", "H2"), ("P3", "H3")]


def _judge_provider(settings):
    if settings.provider == "mock":
        return MockProvider(model=settings.judge_model)
    return GroqProvider(api_key=settings.groq_api_key, model=settings.judge_model)


def main() -> None:
    settings = load_settings()
    orch = Orchestrator.build(settings)
    for h in load_human_answers():
        orch.repo.save_human_answer(h)
    questions = {q.id: q for q in load_questions()}

    evaluator = Evaluator(orch, Judge(_judge_provider(settings)))
    pairs = [(questions[t], questions[h]) for t, h in TWINS]
    ev = evaluator.evaluate(pairs)

    print(f"\n=== Evaluation {ev.eval_id}  (model={ev.model}, judges={ev.judge_prompt_versions}) ===\n")
    header = f"{'Q':<4}{'phase':<9}{'sim v1>v2':<13}{'rc v1>v2':<13}{'evid v1>v2':<13}{'blended v1>v2':<15}{'abl':<6}{'eutil':<6}"
    print(header)
    print("-" * len(header))
    for s in ev.scores:
        abl = f"{s.ablation_blended:.2f}" if s.ablation_blended is not None else "-"
        print(f"{s.question_id:<4}{s.phase:<9}"
              f"{s.similarity_v1:.2f}>{s.similarity_v2:.2f}   "
              f"{s.root_cause_v1:.2f}>{s.root_cause_v2:.2f}   "
              f"{s.evidence_v1:.2f}>{s.evidence_v2:.2f}   "
              f"{s.blended_v1:.2f}>{s.blended_v2:.2f}     {abl:<6}{s.evidence_utilization:<6.2f}")
    util = [s.evidence_utilization for s in ev.scores if s.newly_retrieved_ids]
    if util:
        print(f"\nmean evidence_utilization (where new evidence existed): {sum(util)/len(util):.2f}")

    print("\n--- Gates ---")
    for g in ev.gates:
        tag = "CENTRAL" if g.central else "support"
        status = "PASS" if g.passed else "FAIL"
        print(f"[{status}] {g.name:<28} ({tag})  value={g.value}  threshold={g.threshold}  — {g.detail}")

    print(f"\nCentral claim (held-out improvement + leakage-free): "
          f"{'PASS' if ev.central_claim_passed else 'FAIL'}")
    print(f"Overall verdict (all gates): {'PASS' if ev.verdict else 'FAIL'}")
    orch.repo.close()


if __name__ == "__main__":
    main()
