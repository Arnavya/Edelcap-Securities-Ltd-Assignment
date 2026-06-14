"""Hybrid evaluator + anti-memorization gates.

Per twin family it: runs the train learning cycle (V1->V2 on the train question) and
the held-out transfer (baseline V1 vs post-learning V2 on the twin) plus an ablation
(V2 with learning stripped). Answers are scored with the LLM judges (similarity,
rubric root-cause) and deterministic evidence recall. The success signal is
**rubric coverage + similarity** (blended), and the central claim is **held-out
improvement + leakage-free learning**.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..models import (
    Answer,
    EvaluationRun,
    GateResult,
    HumanAnswer,
    Question,
    QuestionScore,
)
from ..orchestrator import Orchestrator
from .evidence_overlap import compute_overlap
from .improvement import blended, relative_improvement
from .judge import Judge
from .leakage import contains_verbatim

# Thresholds (targets to aim for; partial achievement is still informative).
HELDOUT_IMPROVEMENT_MIN = 0.10   # G1: mean held-out blended lift
ABLATION_DROP_MIN = 0.10         # G2: post-learning minus ablation
SAME_QUESTION_IMPROVEMENT_MIN = 0.20  # G4: mean train relative improvement


class Evaluator:
    def __init__(self, orchestrator: Orchestrator, judge: Judge) -> None:
        self.orch = orchestrator
        self.repo = orchestrator.repo
        self.judge = judge

    # --- scoring ---
    def _score(self, question: Question, answer: Answer, human: HumanAnswer, run_id: str) -> tuple[float, float, float]:
        sim = self.judge.similarity(question, answer, human)
        rc = self.judge.root_cause(question, answer, human)
        self.repo.save_judge_result(run_id, sim)
        self.repo.save_judge_result(run_id, rc)
        evidence = compute_overlap(answer.cited_source_ids, human.key_source_ids).recall
        return sim.score, rc.score, evidence

    @staticmethod
    def _utilization(v2: Answer, newly_retrieved: list[str]) -> float:
        new = set(newly_retrieved)
        if not new:
            return 0.0
        used = set(v2.cited_source_ids)
        for step in v2.reasoning_trace.steps:
            used.update(step.cited_source_ids)
        return round(len(new & used) / len(new), 4)

    def _question_score(self, question, human, v1, v2, run_id, phase, *,
                        newly_retrieved=None, newly_cited=None, ablation=None) -> QuestionScore:
        newly_retrieved = newly_retrieved or []
        s1, r1, e1 = self._score(question, v1, human, run_id)
        s2, r2, e2 = self._score(question, v2, human, run_id)
        b1, b2 = blended(s1, r1), blended(s2, r2)
        ablation_blended = None
        if ablation is not None:
            sa, ra, _ = self._score(question, ablation, human, run_id)
            ablation_blended = blended(sa, ra)
        return QuestionScore(
            question_id=question.id, family_id=question.family_id, is_held_out=question.is_held_out,
            phase=phase,
            similarity_v1=s1, similarity_v2=s2, root_cause_v1=r1, root_cause_v2=r2,
            evidence_v1=e1, evidence_v2=e2, blended_v1=b1, blended_v2=b2,
            ablation_blended=ablation_blended,
            improvement_rel=relative_improvement(b1, b2),
            evidence_utilization=self._utilization(v2, newly_retrieved),
            newly_retrieved_ids=newly_retrieved, newly_cited_ids=newly_cited or [],
        )

    # --- main protocol ---
    def evaluate(self, twin_pairs: list[tuple[Question, Question]]) -> EvaluationRun:
        scores: list[QuestionScore] = []
        for train_q, held_q in twin_pairs:
            train_run = self.orch.run_learning_cycle(train_q)
            scores.append(self._question_score(
                train_q, train_run.human, train_run.v1, train_run.v2, train_run.run_id, "train",
                newly_retrieved=train_run.newly_retrieved_ids, newly_cited=train_run.newly_cited_ids,
            ))

            held_run = self.orch.run_heldout(held_q)
            ablation_answer, _ = self.orch.run_ablation(held_q)
            held_human = self.repo.get_human_answer(held_q.id)
            scores.append(self._question_score(
                held_q, held_human, held_run.v1, held_run.v2, held_run.run_id, "heldout",
                newly_retrieved=held_run.newly_retrieved_ids, newly_cited=held_run.newly_cited_ids,
                ablation=ablation_answer,
            ))

        gates = self._gates(scores)
        verdict = all(g.passed for g in gates)
        central = all(g.passed for g in gates if g.central)
        evaluation = EvaluationRun(
            eval_id=f"eval-{uuid4().hex[:8]}",
            model=self.orch.investigator._provider.model,
            judge_prompt_versions=self.judge.prompt_versions,
            scores=scores, gates=gates, verdict=verdict, central_claim_passed=central,
            created_at=datetime.now(timezone.utc),
        )
        self.repo.save_evaluation_run(evaluation)
        return evaluation

    # --- the four explicit gates ---
    def _gates(self, scores: list[QuestionScore]) -> list[GateResult]:
        held = [s for s in scores if s.phase == "heldout"]
        train = [s for s in scores if s.phase == "train"]

        # G1 — Held-out generalization (CENTRAL): post-learning beats baseline.
        deltas = [s.blended_v2 - s.blended_v1 for s in held]
        mean_delta = sum(deltas) / len(deltas) if deltas else 0.0
        g1 = GateResult(
            name="held_out_generalization", central=True,
            value=round(mean_delta, 4), threshold=HELDOUT_IMPROVEMENT_MIN,
            passed=bool(held) and mean_delta >= HELDOUT_IMPROVEMENT_MIN and all(d > 0 for d in deltas),
            detail=f"mean held-out blended lift over baseline across {len(held)} twins",
        )

        # G2 — Ablation attribution: lift disappears when learning is stripped.
        ab = [(s.blended_v2 - s.ablation_blended) for s in held if s.ablation_blended is not None]
        mean_ab = sum(ab) / len(ab) if ab else 0.0
        g2 = GateResult(
            name="ablation_attribution", central=False,
            value=round(mean_ab, 4), threshold=ABLATION_DROP_MIN,
            passed=bool(ab) and mean_ab >= ABLATION_DROP_MIN,
            detail="post-learning minus learning-stripped (held-out)",
        )

        # G3 — Leakage-free learning (CENTRAL): no event shares an n-gram with its expert answer.
        violations = self._leakage_violations()
        g3 = GateResult(
            name="leakage_free_learning", central=True,
            value=float(violations), threshold=0.0, passed=violations == 0,
            detail="learning-event fields vs expert answers (n-gram overlap)",
        )

        # G4 — Same-question improvement (necessary check).
        imps = [s.improvement_rel for s in train]
        mean_imp = sum(imps) / len(imps) if imps else 0.0
        g4 = GateResult(
            name="same_question_improvement", central=False,
            value=round(mean_imp, 4), threshold=SAME_QUESTION_IMPROVEMENT_MIN,
            passed=bool(train) and mean_imp >= SAME_QUESTION_IMPROVEMENT_MIN,
            detail="mean relative V1->V2 improvement on train questions",
        )
        return [g1, g2, g3, g4]

    def _leakage_violations(self) -> int:
        violations = 0
        for event in self.repo.list_learning_events():
            human = self.repo.get_human_answer(event.source_question_id)
            if human is None:
                continue
            for p in event.patterns:
                if contains_verbatim(p.hint_text, human.answer_text) or contains_verbatim(p.trigger_conditions, human.answer_text):
                    violations += 1
        return violations
