"""SQLite implementation of the Repository.

Generated artifacts (answers, retrieval snapshots, runs) are stored as JSON blobs
in typed-key columns so the dashboard can query by question/version/time without an
ORM. Nothing is overwritten destructively beyond idempotent upserts keyed by id.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import Settings
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
from .repository import Repository

_SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY, family TEXT, family_id TEXT, is_held_out INTEGER, json TEXT
);
CREATE TABLE IF NOT EXISTS human_answers (
    question_id TEXT PRIMARY KEY, json TEXT
);
CREATE TABLE IF NOT EXISTS answers (
    run_id TEXT, question_id TEXT, version TEXT, json TEXT,
    PRIMARY KEY (run_id, question_id, version)
);
CREATE TABLE IF NOT EXISTS retrieval_snapshots (
    run_id TEXT, question_id TEXT, version TEXT, json TEXT,
    PRIMARY KEY (run_id, question_id, version)
);
CREATE TABLE IF NOT EXISTS gap_analyses (
    run_id TEXT, question_id TEXT, version TEXT, json TEXT,
    PRIMARY KEY (run_id, question_id, version)
);
CREATE TABLE IF NOT EXISTS learning_events (
    event_id TEXT PRIMARY KEY, source_question_id TEXT, category TEXT, family_id TEXT, json TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY, question_id TEXT, phase TEXT, created_at TEXT, json TEXT
);
CREATE TABLE IF NOT EXISTS judge_results (
    judge_event_id TEXT PRIMARY KEY, run_id TEXT, metric TEXT, prompt_version TEXT, json TEXT
);
CREATE TABLE IF NOT EXISTS evaluation_runs (
    eval_id TEXT PRIMARY KEY, created_at TEXT, verdict INTEGER, json TEXT
);
"""


class SQLiteRepository(Repository):
    def __init__(self, db_path: str = ":memory:") -> None:
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @classmethod
    def from_settings(cls, settings: Settings) -> "SQLiteRepository":
        return cls(settings.db_path)

    # --- questions ---
    def save_question(self, question: Question) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO questions (id, family, family_id, is_held_out, json) VALUES (?,?,?,?,?)",
            (question.id, question.family.value, question.family_id,
             int(question.is_held_out), question.model_dump_json()),
        )
        self._conn.commit()

    def get_question(self, question_id: str) -> Question | None:
        row = self._conn.execute("SELECT json FROM questions WHERE id=?", (question_id,)).fetchone()
        return Question.model_validate_json(row["json"]) if row else None

    def list_questions(self) -> list[Question]:
        rows = self._conn.execute("SELECT json FROM questions ORDER BY id").fetchall()
        return [Question.model_validate_json(r["json"]) for r in rows]

    # --- human answers ---
    def save_human_answer(self, human: HumanAnswer) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO human_answers (question_id, json) VALUES (?,?)",
            (human.question_id, human.model_dump_json()),
        )
        self._conn.commit()

    def get_human_answer(self, question_id: str) -> HumanAnswer | None:
        row = self._conn.execute("SELECT json FROM human_answers WHERE question_id=?", (question_id,)).fetchone()
        return HumanAnswer.model_validate_json(row["json"]) if row else None

    # --- answers ---
    def save_answer(self, run_id: str, answer: Answer) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO answers (run_id, question_id, version, json) VALUES (?,?,?,?)",
            (run_id, answer.question_id, answer.version.value, answer.model_dump_json()),
        )
        self._conn.commit()

    def get_answers(self, question_id: str) -> list[Answer]:
        rows = self._conn.execute(
            "SELECT json FROM answers WHERE question_id=? ORDER BY version", (question_id,)
        ).fetchall()
        return [Answer.model_validate_json(r["json"]) for r in rows]

    # --- retrieval snapshots ---
    def save_retrieval_snapshot(self, run_id: str, snapshot: RetrievalSnapshot) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO retrieval_snapshots (run_id, question_id, version, json) VALUES (?,?,?,?)",
            (run_id, snapshot.question_id, snapshot.version, snapshot.model_dump_json()),
        )
        self._conn.commit()

    # --- gap analyses ---
    def save_gap_analysis(self, run_id: str, gap: GapAnalysis) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO gap_analyses (run_id, question_id, version, json) VALUES (?,?,?,?)",
            (run_id, gap.question_id, gap.compared_version.value, gap.model_dump_json()),
        )
        self._conn.commit()

    # --- learning events ---
    def save_learning_event(self, event: LearningEvent) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO learning_events (event_id, source_question_id, category, family_id, json) VALUES (?,?,?,?,?)",
            (event.event_id, event.source_question_id,
             event.category.value if event.category else None, event.family_id, event.model_dump_json()),
        )
        self._conn.commit()

    def list_learning_events(self, category: QuestionFamily | None = None) -> list[LearningEvent]:
        if category:
            rows = self._conn.execute(
                "SELECT json FROM learning_events WHERE category=?", (category.value,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT json FROM learning_events").fetchall()
        return [LearningEvent.model_validate_json(r["json"]) for r in rows]

    # --- judge results ---
    def save_judge_result(self, run_id: str, result: JudgeResult) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO judge_results (judge_event_id, run_id, metric, prompt_version, json) VALUES (?,?,?,?,?)",
            (result.judge_event_id, run_id, result.metric, result.judge_prompt_version, result.model_dump_json()),
        )
        self._conn.commit()

    def list_judge_results(self, run_id: str | None = None) -> list[JudgeResult]:
        if run_id:
            rows = self._conn.execute("SELECT json FROM judge_results WHERE run_id=?", (run_id,)).fetchall()
        else:
            rows = self._conn.execute("SELECT json FROM judge_results").fetchall()
        return [JudgeResult.model_validate_json(r["json"]) for r in rows]

    # --- evaluation runs ---
    def save_evaluation_run(self, evaluation: EvaluationRun) -> None:
        created = evaluation.created_at.isoformat() if evaluation.created_at else None
        self._conn.execute(
            "INSERT OR REPLACE INTO evaluation_runs (eval_id, created_at, verdict, json) VALUES (?,?,?,?)",
            (evaluation.eval_id, created, int(evaluation.verdict), evaluation.model_dump_json()),
        )
        self._conn.commit()

    def get_evaluation_run(self, eval_id: str) -> EvaluationRun | None:
        row = self._conn.execute("SELECT json FROM evaluation_runs WHERE eval_id=?", (eval_id,)).fetchone()
        return EvaluationRun.model_validate_json(row["json"]) if row else None

    def latest_evaluation_run(self) -> EvaluationRun | None:
        row = self._conn.execute(
            "SELECT json FROM evaluation_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return EvaluationRun.model_validate_json(row["json"]) if row else None

    # --- runs ---
    def save_run(self, run: RunRecord) -> None:
        created = run.created_at.isoformat() if run.created_at else None
        self._conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, question_id, phase, created_at, json) VALUES (?,?,?,?,?)",
            (run.run_id, run.question_id, run.phase, created, run.model_dump_json()),
        )
        self._conn.commit()

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self._conn.execute("SELECT json FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return RunRecord.model_validate_json(row["json"]) if row else None

    def list_runs(self, question_id: str | None = None) -> list[RunRecord]:
        if question_id:
            rows = self._conn.execute(
                "SELECT json FROM runs WHERE question_id=? ORDER BY created_at", (question_id,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT json FROM runs ORDER BY created_at").fetchall()
        return [RunRecord.model_validate_json(r["json"]) for r in rows]

    def latest_run(self, question_id: str) -> RunRecord | None:
        row = self._conn.execute(
            "SELECT json FROM runs WHERE question_id=? ORDER BY created_at DESC LIMIT 1", (question_id,)
        ).fetchone()
        return RunRecord.model_validate_json(row["json"]) if row else None

    def close(self) -> None:
        self._conn.close()
