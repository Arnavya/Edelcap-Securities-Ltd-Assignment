"""Investigation agent — produces a structured V1/V2 Answer from evidence.

One entry point (``investigate``) is used for both V1 (no learned context) and V2
(expansion terms / routing / heuristics injected). Keeping a single code path means
the only difference between V1 and V2 is the learned context, which isolates the
learning effect for evaluation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..llm import LLMProvider
from ..models import (
    Answer,
    AnswerVersion,
    EvidenceItem,
    Question,
    ReasoningStep,
    ReasoningTrace,
    RetrievalSnapshot,
    SourceType,
)
from ..prompts import load_prompt
from ..retrieval import KnowledgeStore, Retriever
from .json_parsing import extract_json_object

INVESTIGATION_PROMPT_VERSION = "investigation_v1"
INVESTIGATION_V2_PROMPT_VERSION = "investigation_v2"
SYSTEM = "You are a meticulous, evidence-grounded engineering investigator. You never invent facts or citations."
_BODY_CAP = 900
_NEW_MARKER = "[NEW — surfaced via learned guidance] "


def _clamp(value, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(lo, min(hi, f))


def _format_evidence(items: list[EvidenceItem], new_ids: set[str] | None = None) -> str:
    new_ids = new_ids or set()
    blocks = []
    for it in items:
        meta = it.source_type.value + (f", {it.service}" if it.service else "")
        body = it.body if len(it.body) <= _BODY_CAP else it.body[:_BODY_CAP] + " …"
        marker = _NEW_MARKER if it.source_id in new_ids else ""
        blocks.append(f"{marker}[{it.source_id}] ({meta}) {it.title}\n{body}")
    return "\n\n".join(blocks)


class InvestigationAgent:
    def __init__(self, provider: LLMProvider, retriever: Retriever, store: KnowledgeStore) -> None:
        self._provider = provider
        self._retriever = retriever
        self._store = store

    def investigate(
        self,
        question: Question,
        *,
        version: AnswerVersion = AnswerVersion.V1,
        k_per_source: int = 4,
        expansion_terms: list[str] | None = None,
        routing_sources: list[SourceType] | None = None,
        guidance_text: str = "",
        injected_pattern_ids: list[str] | None = None,
    ) -> tuple[Answer, RetrievalSnapshot]:
        snapshot = self._retriever.search(
            question.text,
            k_per_source=k_per_source,
            expansion_terms=expansion_terms,
            routing_sources=routing_sources,
            question_id=question.id,
            version=version.value,
        )
        valid_ids = set(snapshot.source_ids)
        retrieved_items = [self._store.require(sid) for sid in snapshot.source_ids]

        is_v2 = version is AnswerVersion.V2
        prompt_version = INVESTIGATION_V2_PROMPT_VERSION if is_v2 else INVESTIGATION_PROMPT_VERSION
        # Mark evidence that learned guidance surfaced, so V2 can reassess around it.
        new_ids = {it.source_id for it in snapshot.items if it.from_expansion} if is_v2 else set()

        guidance = f"\n{guidance_text}\n" if guidance_text else ""
        prompt = (
            load_prompt(prompt_version)
            .replace("<<QUESTION>>", question.text)
            .replace("<<EVIDENCE>>", _format_evidence(retrieved_items, new_ids))
            .replace("<<GUIDANCE>>", guidance)
        )

        raw = self._provider.generate(prompt, system=SYSTEM, max_tokens=1500)
        data = extract_json_object(raw)

        steps = self._build_steps(data.get("reasoning_steps", []), valid_ids)
        # Answer-level citations: model's, intersected with retrieved, unioned with
        # whatever the steps actually cited (so the trace and citations stay coherent).
        model_cited = [s for s in data.get("cited_source_ids", []) if s in valid_ids]
        step_cited = [sid for st in steps for sid in st.cited_source_ids]
        cited = _ordered_unique(model_cited + step_cited)

        trace = ReasoningTrace(
            steps=steps,
            candidate_root_causes=[str(x) for x in data.get("candidate_root_causes", [])],
            summary=str(data.get("summary", "")),
            applied_heuristic_ids=list(injected_pattern_ids or []),
        )
        answer = Answer(
            question_id=question.id,
            version=version,
            answer_text=str(data.get("answer_text", "")).strip(),
            cited_source_ids=cited,
            reasoning_trace=trace,
            prompt_versions={"investigation": prompt_version},
            provider=self._provider.name,
            model=self._provider.model,
            injected_pattern_ids=list(injected_pattern_ids or []),
            created_at=datetime.now(timezone.utc),
        )
        return answer, snapshot

    @staticmethod
    def _build_steps(raw_steps, valid_ids: set[str]) -> list[ReasoningStep]:
        steps: list[ReasoningStep] = []
        for rs in raw_steps:
            if not isinstance(rs, dict):
                continue
            cited = [s for s in rs.get("cited_source_ids", []) if s in valid_ids]  # drop hallucinations
            steps.append(ReasoningStep(
                claim=str(rs.get("claim", "")).strip(),
                cited_source_ids=cited,
                confidence=_clamp(rs.get("confidence", 0.5)),
            ))
        return steps


def _ordered_unique(seq: list[str]) -> list[str]:
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
