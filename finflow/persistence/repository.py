"""Repository interface for persisted artifacts.

The dashboard reads exclusively through this interface, so it stays a pure
visualization layer (no pipeline logic). The SQLite implementation is the default;
tests use an in-memory instance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import (
    Answer,
    EvaluationRun,
    GapAnalysis,
    HumanAnswer,
    JudgeResult,
    LearningEvent,
    Question,
    QuestionFamily,
    RetrievalSnapshot,
    RunRecord,
)


class Repository(ABC):
    # --- inputs (seeded from the dataset) ---
    @abstractmethod
    def save_question(self, question: Question) -> None: ...

    @abstractmethod
    def get_question(self, question_id: str) -> Question | None: ...

    @abstractmethod
    def list_questions(self) -> list[Question]: ...

    @abstractmethod
    def save_human_answer(self, human: HumanAnswer) -> None: ...

    @abstractmethod
    def get_human_answer(self, question_id: str) -> HumanAnswer | None: ...

    # --- generated artifacts ---
    @abstractmethod
    def save_answer(self, run_id: str, answer: Answer) -> None: ...

    @abstractmethod
    def save_retrieval_snapshot(self, run_id: str, snapshot: RetrievalSnapshot) -> None: ...

    @abstractmethod
    def save_gap_analysis(self, run_id: str, gap: GapAnalysis) -> None: ...

    @abstractmethod
    def save_learning_event(self, event: LearningEvent) -> None: ...

    @abstractmethod
    def list_learning_events(self, category: QuestionFamily | None = None) -> list[LearningEvent]: ...

    @abstractmethod
    def save_judge_result(self, run_id: str, result: JudgeResult) -> None: ...

    @abstractmethod
    def save_evaluation_run(self, evaluation: EvaluationRun) -> None: ...

    @abstractmethod
    def get_evaluation_run(self, eval_id: str) -> EvaluationRun | None: ...

    @abstractmethod
    def latest_evaluation_run(self) -> EvaluationRun | None: ...

    @abstractmethod
    def save_run(self, run: RunRecord) -> None: ...

    @abstractmethod
    def get_run(self, run_id: str) -> RunRecord | None: ...

    @abstractmethod
    def list_runs(self, question_id: str | None = None) -> list[RunRecord]: ...

    @abstractmethod
    def latest_run(self, question_id: str) -> RunRecord | None: ...

    def close(self) -> None:  # optional override
        pass
