"""Gap analysis — compare a V1 answer to the human ground truth.

Two parts, by design:
- **Deterministic** evidence diff: cited vs gold `key_source_ids` (set operations) and
  a deterministic severity. Reproducible, no LLM.
- **LLM** semantic diff (``gap_v1``): reasoning gaps + which rubric root-cause
  elements are uncovered, grounded on the canonical rubric.
"""

from __future__ import annotations

from ..llm import LLMProvider
from ..models import (
    Answer,
    GapAnalysis,
    HumanAnswer,
    Question,
    ReasoningTrace,
)
from ..prompts import load_prompt
from .json_parsing import extract_json_object

GAP_PROMPT_VERSION = "gap_v1"
SYSTEM = "You are a rigorous engineering reviewer. You identify reasoning gaps without parroting the reference answer."


def evidence_diff(cited: list[str], gold: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Return (matched, missed, extra) as sorted lists. Pure/deterministic."""
    cited_set, gold_set = set(cited), set(gold)
    matched = sorted(cited_set & gold_set)
    missed = sorted(gold_set - cited_set)
    extra = sorted(cited_set - gold_set)
    return matched, missed, extra


def severity(missed: list[str], gold: list[str], n_missed_root_causes: int) -> str:
    frac = (len(missed) / len(gold)) if gold else 0.0
    if frac >= 0.5 or n_missed_root_causes >= 2:
        return "high"
    if frac > 0.0 or n_missed_root_causes >= 1:
        return "medium"
    return "low"


def _format_reasoning(trace: ReasoningTrace) -> str:
    lines = [f"- ({s.confidence:.2f}) {s.claim} {s.cited_source_ids}" for s in trace.steps]
    if trace.candidate_root_causes:
        lines.append("candidate_root_causes: " + "; ".join(trace.candidate_root_causes))
    return "\n".join(lines) or "(no reasoning steps)"


class GapAnalysisAgent:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def analyze(self, question: Question, answer: Answer, human: HumanAnswer) -> GapAnalysis:
        matched, missed, extra = evidence_diff(answer.cited_source_ids, human.key_source_ids)

        rubric_text = "\n".join(f"- [{e.id}] {e.description}" for e in human.root_cause_rubric) or "(none)"
        prompt = (
            load_prompt(GAP_PROMPT_VERSION)
            .replace("<<QUESTION>>", question.text)
            .replace("<<AI_ANSWER>>", answer.answer_text or "(empty)")
            .replace("<<AI_REASONING>>", _format_reasoning(answer.reasoning_trace))
            .replace("<<HUMAN_ANSWER>>", human.answer_text)
            .replace("<<RUBRIC>>", rubric_text)
            .replace("<<MISSED_EVIDENCE>>", ", ".join(missed) or "(none)")
        )
        data = extract_json_object(self._provider.generate(prompt, system=SYSTEM, max_tokens=1000))

        reasoning_gaps = [str(x) for x in data.get("reasoning_gaps", [])]
        missed_root_causes = [str(x) for x in data.get("missed_root_causes", [])]
        narrative = str(data.get("narrative", ""))

        return GapAnalysis(
            question_id=question.id,
            compared_version=answer.version,
            reasoning_gaps=reasoning_gaps,
            missed_evidence_ids=missed,
            extra_evidence_ids=extra,
            missed_root_causes=missed_root_causes,
            severity=severity(missed, human.key_source_ids, len(missed_root_causes)),
            narrative=narrative,
        )
