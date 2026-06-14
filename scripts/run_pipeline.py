"""Run the V1 investigation for one question and persist the result.

Usage:
    python scripts/run_pipeline.py --question P2
    FINFLOW_PROVIDER=mock python scripts/run_pipeline.py --question P2   # offline
"""

from __future__ import annotations

import argparse

from finflow.config import load_settings
from finflow.orchestrator import Orchestrator
from finflow.retrieval import load_questions


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a V1 investigation.")
    parser.add_argument("--question", required=True, help="Question id, e.g. P2")
    args = parser.parse_args()

    settings = load_settings()
    questions = {q.id: q for q in load_questions()}
    if args.question not in questions:
        raise SystemExit(f"unknown question id '{args.question}'. Known: {', '.join(questions)}")

    orch = Orchestrator.build(settings)
    run = orch.run_v1(questions[args.question])
    ans = run.v1

    print(f"\n=== {args.question} ({run.v1.question_id}) — V1 [{ans.provider}:{ans.model}] ===")
    print(f"run_id: {run.run_id}")
    print(f"\nRetrieved ({len(run.retrieval_v1.items)}): {run.retrieval_v1.source_ids}")
    print(f"\nAnswer:\n{ans.answer_text}")
    print(f"\nCitations: {ans.cited_source_ids}")
    print("\nReasoning steps:")
    for i, step in enumerate(ans.reasoning_trace.steps, 1):
        print(f"  {i}. ({step.confidence:.2f}) {step.claim}  {step.cited_source_ids}")
    print(f"\nCandidate root causes: {ans.reasoning_trace.candidate_root_causes}")

    if run.human is not None:
        gap = orch.add_gap_analysis(run)
        print("\n--- Gap analysis (vs expert) ---")
        print(f"severity: {gap.severity}")
        print(f"missed evidence: {gap.missed_evidence_ids}")
        print(f"extra evidence:  {gap.extra_evidence_ids}")
        print(f"missed root causes: {gap.missed_root_causes}")
        print(f"reasoning gaps: {gap.reasoning_gaps}")

    orch.repo.close()


if __name__ == "__main__":
    main()
