"""Dashboard data layer — pure view-model builders over the repository.

Strictly READ-ONLY: it only reads persisted artifacts (runs, retrieval snapshots
embedded in runs, gap analyses, learning events, evaluation runs, judge results).
It NEVER runs a pipeline, judge, or learning step. No Streamlit/pandas imports here
so it stays unit-testable; the view layer (app.py) handles rendering.
"""

from __future__ import annotations

from finflow.config import load_settings
from finflow.models import EvaluationRun, LearningEvent, RunRecord
from finflow.persistence import SQLiteRepository


def open_repo(db_path: str | None = None) -> SQLiteRepository:
    settings = load_settings()
    return SQLiteRepository(db_path or settings.db_path)


# --- Section 1: question feed -------------------------------------------------

def question_feed(repo: SQLiteRepository) -> list[dict]:
    rows = []
    for q in repo.list_questions():
        runs = repo.list_runs(q.id)
        rows.append({
            "id": q.id,
            "family": q.family.value,
            "held_out": q.is_held_out,
            "text": q.text,
            "n_runs": len(runs),
            "has_v2": any(r.v2 is not None for r in runs),
        })
    return rows


def latest_run(repo: SQLiteRepository, question_id: str) -> RunRecord | None:
    return repo.latest_run(question_id)


# --- Sections 2-7: a single run's detail -------------------------------------

def evidence_comparison(run: RunRecord) -> list[dict]:
    """V1 vs V2 retrieved/cited evidence, flagging newly-retrieved and newly-cited."""
    v1 = set(run.retrieval_v1.source_ids) if run.retrieval_v1 else set()
    v2 = set(run.retrieval_v2.source_ids) if run.retrieval_v2 else set()
    c1 = set(run.v1.cited_source_ids) if run.v1 else set()
    c2 = set(run.v2.cited_source_ids) if run.v2 else set()
    rows = []
    for sid in sorted(v1 | v2 | c1 | c2):
        rows.append({
            "source_id": sid,
            "retrieved_v1": sid in v1,
            "retrieved_v2": sid in v2,
            "newly_retrieved": sid in (v2 - v1),
            "cited_v1": sid in c1,
            "cited_v2": sid in c2,
            "newly_cited": sid in (c2 - c1),
        })
    return rows


def evidence_utilization(run: RunRecord) -> float | None:
    """Fraction of newly-retrieved evidence actually referenced by V2."""
    if run.v2 is None or not run.newly_retrieved_ids:
        return None
    new = set(run.newly_retrieved_ids)
    used = set(run.v2.cited_source_ids)
    for step in run.v2.reasoning_trace.steps:
        used.update(step.cited_source_ids)
    return round(len(new & used) / len(new), 4)


def reasoning_steps(answer) -> list[dict]:
    if answer is None:
        return []
    return [{"claim": s.claim, "confidence": s.confidence, "cited": s.cited_source_ids}
            for s in answer.reasoning_trace.steps]


def retrieval_trace(snapshot) -> dict | None:
    """Inspectable retrieval: ranked items + diagnostics."""
    if snapshot is None:
        return None
    return {
        "query": snapshot.query,
        "items": [{"rank": it.rank, "source_id": it.source_id, "type": it.source_type.value,
                   "score": it.score, "from_expansion": it.from_expansion,
                   "matched_terms": it.matched_terms} for it in snapshot.items],
        "diagnostics": snapshot.diagnostics.model_dump(),
    }


def run_detail(repo: SQLiteRepository, run: RunRecord) -> dict:
    return {
        "run_id": run.run_id,
        "question_id": run.question_id,
        "phase": run.phase,
        "v1": run.v1.answer_text if run.v1 else None,
        "v2": run.v2.answer_text if run.v2 else None,
        "expert": run.human.answer_text if run.human else None,
        "gap": run.gap.model_dump() if run.gap else None,
        "learning_event": learning_event_view(run.learning_event) if run.learning_event else None,
        "evidence_comparison": evidence_comparison(run),
        "evidence_utilization": evidence_utilization(run),
        "newly_retrieved_ids": run.newly_retrieved_ids,
        "newly_cited_ids": run.newly_cited_ids,
        "retrieval_v1": retrieval_trace(run.retrieval_v1),
        "retrieval_v2": retrieval_trace(run.retrieval_v2),
        "v1_steps": reasoning_steps(run.v1),
        "v2_steps": reasoning_steps(run.v2),
        "judge_results": [j.model_dump() for j in repo.list_judge_results(run.run_id)],
    }


# --- Section: learning event --------------------------------------------------

def learning_event_view(event: LearningEvent) -> dict:
    by_type: dict[str, list[dict]] = {}
    for p in event.patterns:
        by_type.setdefault(p.pattern_type.value, []).append({
            "id": p.id, "hint_text": p.hint_text, "routing_sources": [s.value for s in p.routing_sources],
            "retrieval_signals": p.retrieval_signals, "applies_to_services": p.applies_to_services,
            "trigger_conditions": p.trigger_conditions, "confidence": p.confidence,
        })
    return {
        "event_id": event.event_id,
        "source_question_id": event.source_question_id,
        "category": event.category.value if event.category else None,
        "patterns_by_type": by_type,
        "n_patterns": len(event.patterns),
        "leakage": {
            "passed": event.sanitization.leakage_check_passed,
            "max_ngram_overlap": event.sanitization.max_ngram_overlap,
            "redactions": event.sanitization.redactions,
        },
    }


def all_learning_events(repo: SQLiteRepository) -> list[dict]:
    return [learning_event_view(e) for e in repo.list_learning_events()]


# --- Sections 8-9: evaluation, metrics, transfer -----------------------------

def evaluation_summary(repo: SQLiteRepository) -> dict | None:
    ev = repo.latest_evaluation_run()
    return evaluation_view(ev) if ev else None


def evaluation_view(ev: EvaluationRun) -> dict:
    scores = [{
        "question_id": s.question_id, "phase": s.phase, "is_held_out": s.is_held_out,
        "similarity_v1": s.similarity_v1, "similarity_v2": s.similarity_v2,
        "root_cause_v1": s.root_cause_v1, "root_cause_v2": s.root_cause_v2,
        "evidence_v1": s.evidence_v1, "evidence_v2": s.evidence_v2,
        "blended_v1": s.blended_v1, "blended_v2": s.blended_v2,
        "ablation_blended": s.ablation_blended,
        "evidence_utilization": s.evidence_utilization,
        "improvement_rel": s.improvement_rel,
        "newly_retrieved_ids": s.newly_retrieved_ids,
        "newly_cited_ids": s.newly_cited_ids,
    } for s in ev.scores]
    return {
        "eval_id": ev.eval_id, "model": ev.model,
        "judge_prompt_versions": ev.judge_prompt_versions,
        "verdict": ev.verdict, "central_claim_passed": ev.central_claim_passed,
        "scores": scores,
        "gates": [g.model_dump() for g in ev.gates],
    }


def transfer_metrics(ev: EvaluationRun) -> list[dict]:
    """Per held-out twin: baseline vs post-learning, deltas, ablation, utilization."""
    rows = []
    for s in ev.scores:
        if s.phase != "heldout":
            continue
        rows.append({
            "question_id": s.question_id,
            "blended_v1": s.blended_v1, "blended_v2": s.blended_v2,
            "held_out_delta": round(s.blended_v2 - s.blended_v1, 4),
            "ablation_blended": s.ablation_blended,
            "ablation_delta": round(s.blended_v2 - s.ablation_blended, 4) if s.ablation_blended is not None else None,
            "root_cause_v1": s.root_cause_v1, "root_cause_v2": s.root_cause_v2,
            "evidence_utilization": s.evidence_utilization,
        })
    return rows


def metrics_chart_frame(ev: EvaluationRun) -> list[dict]:
    """Long-form rows for a V1-vs-V2 blended bar chart."""
    rows = []
    for s in ev.scores:
        rows.append({"question_id": s.question_id, "version": "V1", "blended": s.blended_v1})
        rows.append({"question_id": s.question_id, "version": "V2", "blended": s.blended_v2})
    return rows
