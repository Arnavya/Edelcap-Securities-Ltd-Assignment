"""Seed the SQLite database with the dataset inputs (questions + human answers).

Generated artifacts (answers, runs) are written by the pipeline, not here.
Usage: python scripts/seed_db.py
"""

from __future__ import annotations

from finflow.config import load_settings
from finflow.persistence import SQLiteRepository
from finflow.retrieval import load_human_answers, load_questions


def main() -> None:
    settings = load_settings()
    repo = SQLiteRepository.from_settings(settings)

    questions = load_questions()
    for q in questions:
        repo.save_question(q)
    humans = load_human_answers()
    for h in humans:
        repo.save_human_answer(h)

    print(f"Seeded {len(questions)} questions and {len(humans)} human answers into {settings.db_path}")
    repo.close()


if __name__ == "__main__":
    main()
