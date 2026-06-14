"""Learning event generator — distill a gap into reusable, answer-free patterns.

Structural anti-leakage: the extractor is given the *abstracted gap* (not the raw
expert answer), so it cannot copy it. Deterministic anti-leakage: every produced
pattern is run through the sanitization gate, which DROPS any pattern sharing an
n-gram with the expert answer. The event persists only if it is verbatim-free.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from ..evaluation import sanitize_patterns
from ..llm import LLMProvider
from ..models import (
    Answer,
    GapAnalysis,
    HumanAnswer,
    LearningEvent,
    LearningPattern,
    PatternType,
    Question,
    Sanitization,
    SourceType,
)
from ..models.learning import MetricSnapshot
from ..prompts import load_prompt
from ..retrieval import KnowledgeStore
from .json_parsing import extract_json_object

LEARNING_PROMPT_VERSION = "learning_extract_v2"
SYSTEM = "You distill reusable investigative methods. You never reproduce the specific answer or expert wording."


def fingerprint(question: Question) -> str:
    payload = f"{question.family.value}:{question.text}".lower().encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _coerce_sources(values) -> list[SourceType]:
    out = []
    for v in values or []:
        try:
            out.append(SourceType(str(v).lower()))
        except ValueError:
            continue
    return out


def _coerce_pattern_type(value) -> PatternType:
    try:
        return PatternType(str(value).lower())
    except ValueError:
        return PatternType.EXPERT_HEURISTIC


class LearningEventGenerator:
    def __init__(self, provider: LLMProvider, store: KnowledgeStore) -> None:
        self._provider = provider
        self._store = store

    def generate(
        self, question: Question, v1: Answer, gap: GapAnalysis, human: HumanAnswer
    ) -> LearningEvent:
        missed_lines = []
        for sid in gap.missed_evidence_ids:
            item = self._store.get(sid)
            if item:
                missed_lines.append(f"{item.source_id} | {item.source_type.value} | {item.title}")
        missed_block = "\n".join(missed_lines) or "(none)"

        prompt = (
            load_prompt(LEARNING_PROMPT_VERSION)
            .replace("<<FAMILY>>", question.family.value)
            .replace("<<QUESTION>>", question.text)
            .replace("<<AI_ANSWER>>", v1.answer_text or "(empty)")
            .replace("<<AI_ROOT_CAUSES>>", "; ".join(v1.reasoning_trace.candidate_root_causes) or "(none)")
            .replace("<<REASONING_GAPS>>", "; ".join(gap.reasoning_gaps) or "(none)")
            .replace("<<MISSED_ROOT_CAUSES>>", "; ".join(gap.missed_root_causes) or "(none)")
            .replace("<<MISSED_EVIDENCE>>", missed_block)
        )
        data = extract_json_object(self._provider.generate(prompt, system=SYSTEM, max_tokens=1200))

        patterns = self._build_patterns(data.get("patterns", []), question)
        kept, dropped, max_overlap = sanitize_patterns(patterns, human.answer_text)

        return LearningEvent(
            event_id=uuid4().hex,
            source_question_id=question.id,
            family_id=question.family_id,
            category=question.family,
            question_fingerprint=fingerprint(question),
            provider_model=f"{self._provider.name}:{self._provider.model}",
            prompt_version=LEARNING_PROMPT_VERSION,
            patterns=kept,
            metric_snapshot=MetricSnapshot(),  # filled in P7
            sanitization=Sanitization(
                leakage_check_passed=True,  # guaranteed: leaking patterns were dropped
                max_ngram_overlap=max_overlap,
                redactions=dropped,
            ),
            created_at=datetime.now(timezone.utc),
        )

    def _build_patterns(self, raw_patterns, question: Question) -> list[LearningPattern]:
        patterns: list[LearningPattern] = []
        for i, rp in enumerate(raw_patterns, start=1):
            if not isinstance(rp, dict):
                continue
            patterns.append(LearningPattern(
                id=f"lp-{i}",
                pattern_type=_coerce_pattern_type(rp.get("pattern_type")),
                applies_to_family=question.family,
                applies_to_services=[str(s) for s in rp.get("applies_to_services", [])],
                hint_text=str(rp.get("hint_text", "")).strip(),
                routing_sources=_coerce_sources(rp.get("routing_sources")),
                retrieval_signals=[str(s) for s in rp.get("retrieval_signals", [])],
                trigger_conditions=str(rp.get("trigger_conditions", "")).strip(),
                confidence=float(rp.get("confidence", 0.5)) if str(rp.get("confidence", "")).replace(".", "", 1).isdigit() else 0.5,
            ))
        return patterns
