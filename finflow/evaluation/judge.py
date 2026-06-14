"""LLM-as-judge for answer similarity and rubric-based root-cause coverage.

Both judges are versioned (prompt stem) and every evaluation returns a fully-logged
``JudgeResult`` (score in [0,1] + reasoning + structured detail + prompt version +
model). Root-cause coverage is the success signal — scored element-by-element against
the per-question rubric, which tames judge variance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..agents.json_parsing import extract_json_object
from ..llm import LLMProvider
from ..models import Answer, HumanAnswer, JudgeResult, Question
from ..prompts import load_prompt

SIMILARITY_PROMPT_VERSION = "judge_similarity_v2"
ROOT_CAUSE_PROMPT_VERSION = "judge_root_cause_v1"
SYSTEM = "You are a strict, consistent evaluation judge. You output only JSON."

_VERDICT_SCORE = {"hit": 1.0, "partial": 0.5, "miss": 0.0}


def _clamp01(x) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


class Judge:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def similarity(self, question: Question, answer: Answer, human: HumanAnswer) -> JudgeResult:
        prompt = (
            load_prompt(SIMILARITY_PROMPT_VERSION)
            .replace("<<QUESTION>>", question.text)
            .replace("<<REFERENCE>>", human.answer_text)
            .replace("<<CANDIDATE>>", answer.answer_text or "(empty)")
        )
        data = extract_json_object(self._provider.generate(prompt, system=SYSTEM, max_tokens=700))
        score = _clamp01(float(data.get("score", 0)) / 100.0)
        return JudgeResult(
            judge_event_id=uuid4().hex,
            metric="answer_similarity",
            score=round(score, 4),
            reasoning=str(data.get("reasoning", "")),
            structured_detail={"covered_points": data.get("covered_points", []),
                               "missed_points": data.get("missed_points", [])},
            judge_prompt_version=SIMILARITY_PROMPT_VERSION,
            judge_model=f"{self._provider.name}:{self._provider.model}",
            created_at=datetime.now(timezone.utc),
        )

    def root_cause(self, question: Question, answer: Answer, human: HumanAnswer) -> JudgeResult:
        rubric = "\n".join(f"- [{e.id}] {e.description}" for e in human.root_cause_rubric) or "(none)"
        prompt = (
            load_prompt(ROOT_CAUSE_PROMPT_VERSION)
            .replace("<<QUESTION>>", question.text)
            .replace("<<CANDIDATE>>", answer.answer_text or "(empty)")
            .replace("<<RUBRIC>>", rubric)
        )
        data = extract_json_object(self._provider.generate(prompt, system=SYSTEM, max_tokens=900))
        per_element = data.get("per_element", [])
        # Recompute the average from per-element verdicts for determinism/robustness.
        if per_element:
            vals = []
            for el in per_element:
                if "score" in el:
                    vals.append(_clamp01(el["score"]))
                else:
                    vals.append(_VERDICT_SCORE.get(str(el.get("verdict", "")).lower(), 0.0))
            score = sum(vals) / len(vals)
        else:
            score = _clamp01(data.get("score", 0))
        return JudgeResult(
            judge_event_id=uuid4().hex,
            metric="root_cause_coverage",
            score=round(score, 4),
            reasoning=str(data.get("reasoning", "")),
            structured_detail={"per_element": per_element},
            judge_prompt_version=ROOT_CAUSE_PROMPT_VERSION,
            judge_model=f"{self._provider.name}:{self._provider.model}",
            created_at=datetime.now(timezone.utc),
        )

    @property
    def prompt_versions(self) -> dict[str, str]:
        return {"similarity": SIMILARITY_PROMPT_VERSION, "root_cause": ROOT_CAUSE_PROMPT_VERSION}
