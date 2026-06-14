"""Learning memory — store and retrieve answer-free learning events.

The memory holds only ``LearningEvent``s (no answer field; sanitized patterns), so
it is structurally answer-free. For a new question it aggregates the relevant
patterns into a ``LearnedContext`` with TWO independently-consumed categories:
- retrieval signals (expansion_terms) → widen retrieval,
- reasoning heuristics → injected into the investigation prompt,
plus source-routing bias. A deterministic relevance score gates which patterns are
injected, so weakly-relevant (e.g. service-specific) patterns don't bleed across.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import LearningEvent, LearningPattern, PatternType, Question, SourceType
from ..persistence import Repository

RELEVANCE_THRESHOLD = 0.65


@dataclass
class LearnedContext:
    routing_sources: list[SourceType] = field(default_factory=list)
    expansion_terms: list[str] = field(default_factory=list)       # retrieval signals
    reasoning_heuristics: list[str] = field(default_factory=list)  # reasoning methods
    guidance_text: str = ""
    pattern_ids: list[str] = field(default_factory=list)
    source_event_ids: list[str] = field(default_factory=list)
    applied_patterns: list[dict] = field(default_factory=list)     # diagnostics
    rejected_patterns: list[dict] = field(default_factory=list)    # diagnostics

    @property
    def is_empty(self) -> bool:
        return not (self.routing_sources or self.expansion_terms or self.reasoning_heuristics)

    def diagnostic_notes(self) -> list[str]:
        notes = []
        for a in self.applied_patterns:
            notes.append(f"applied {a['pattern_id']} (relevance {a['score']})")
        for r in self.rejected_patterns:
            notes.append(f"rejected {r['pattern_id']} (relevance {r['score']}): {r['reason']}")
        return notes


def relevance_score(pattern: LearningPattern, question: Question) -> float:
    """Deterministic relevance of a learned pattern to a question.

    Same family is the precondition (memory already filters by family). Service-
    specific patterns must overlap the question's tags to earn their weight;
    service-agnostic (general) patterns get partial credit so they can transfer.
    """
    score = 0.0
    if pattern.applies_to_family == question.family:
        score += 0.6
    q_tags = {t.lower() for t in question.tags}
    if pattern.applies_to_services:
        svc = {s.lower() for s in pattern.applies_to_services}
        score += 0.4 if (svc & q_tags) else 0.0   # specific + matches; mismatch earns nothing
    else:
        score += 0.3                               # general lesson: broadly applicable
    return round(min(score, 1.0), 3)


def _dedupe(seq):
    seen, out = set(), []
    for x in seq:
        key = x.value if isinstance(x, SourceType) else x
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out


class LearningMemory:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def store(self, event: LearningEvent) -> None:
        self._repo.save_learning_event(event)

    def context_for(self, question: Question, *, exclude_question_ids: set[str] | None = None) -> LearnedContext:
        exclude = exclude_question_ids or set()
        events = [
            e for e in self._repo.list_learning_events(category=question.family)
            if e.source_question_id not in exclude
        ]
        patterns = [(e, p) for e in events for p in e.patterns]
        patterns.sort(key=lambda ep: (-ep[1].confidence, ep[0].event_id, ep[1].id))

        routing: list[SourceType] = []
        expansion: list[str] = []
        heuristics: list[str] = []
        pattern_ids: list[str] = []
        applied: list[dict] = []
        rejected: list[dict] = []

        for event, p in patterns:
            score = relevance_score(p, question)
            if score < RELEVANCE_THRESHOLD:
                rejected.append({"pattern_id": p.id, "score": score,
                                 "reason": "low relevance (service/tag mismatch for this question)"})
                continue
            applied.append({"pattern_id": p.id, "score": score, "event_id": event.event_id})
            pattern_ids.append(p.id)
            routing.extend(p.routing_sources)
            expansion.extend(p.retrieval_signals)
            if p.pattern_type in (PatternType.EXPERT_HEURISTIC, PatternType.REASONING_GAP) and p.hint_text:
                heuristics.append(p.hint_text)

        heuristics = _dedupe(heuristics)
        guidance = ""
        if heuristics:
            guidance = (
                "LEARNED GUIDANCE (reasoning heuristics — apply if the triggers match; do not invent facts):\n"
                + "\n".join(f"- {h}" for h in heuristics)
            )

        return LearnedContext(
            routing_sources=_dedupe(routing),
            expansion_terms=_dedupe(expansion),
            reasoning_heuristics=heuristics,
            guidance_text=guidance,
            pattern_ids=_dedupe(pattern_ids),
            source_event_ids=_dedupe([e.event_id for e in events]),
            applied_patterns=applied,
            rejected_patterns=rejected,
        )
