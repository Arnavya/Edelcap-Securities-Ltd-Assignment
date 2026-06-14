"""P2: validate the authored synthetic corpus (no loaders yet — read JSON directly)."""

import json
from pathlib import Path

import pytest

from finflow.models import EvidenceItem, HumanAnswer, Question

DATA = Path(__file__).resolve().parent.parent / "data"
SOURCES = DATA / "sources"

EXPECTED_COUNTS = {
    "slack_threads.json": 14,
    "tickets.json": 14,
    "wiki.json": 8,
    "commits.json": 18,
}
DISTRACTORS = {
    "slack:inc-may-latency", "slack:risk-model-v4-rollout",
    "ticket:PAY-505", "ticket:RISK-260",
    "commit:b1", "commit:b2", "commit:b3",
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def evidence() -> dict[str, EvidenceItem]:
    items: dict[str, EvidenceItem] = {}
    for fname in EXPECTED_COUNTS:
        for raw in _load(SOURCES / fname):
            item = EvidenceItem.model_validate(raw)  # validates every field
            items[item.source_id] = item
    return items


def test_source_counts():
    for fname, expected in EXPECTED_COUNTS.items():
        assert len(_load(SOURCES / fname)) == expected, fname


def test_total_corpus_is_54(evidence):
    assert len(evidence) == 54  # 47 answer-chain + 7 distractors


def test_all_source_ids_unique():
    seen, dupes = set(), []
    for fname in EXPECTED_COUNTS:
        for raw in _load(SOURCES / fname):
            sid = raw["source_id"]
            (dupes.append(sid) if sid in seen else seen.add(sid))
    assert not dupes, f"duplicate source_ids: {dupes}"


def test_every_item_has_full_metadata(evidence):
    """Required, non-empty: source_id, source_type, title, body, tags, created_at, author."""
    for item in evidence.values():
        assert item.source_id and item.title and item.body
        assert item.tags, f"{item.source_id} has no tags"
        assert item.created_at is not None, f"{item.source_id} missing created_at"
        assert item.author, f"{item.source_id} missing author"


def test_distractors_present(evidence):
    assert DISTRACTORS.issubset(evidence.keys())


@pytest.fixture(scope="module")
def questions() -> dict[str, Question]:
    return {q.id: q for q in (Question.model_validate(raw) for raw in _load(DATA / "feed.json"))}


@pytest.fixture(scope="module")
def humans() -> dict[str, HumanAnswer]:
    return {h.question_id: h for h in (HumanAnswer.model_validate(raw) for raw in _load(DATA / "human_answers.json"))}


def test_feed_has_six_primary_three_heldout(questions):
    assert len(questions) == 9
    held = [q for q in questions.values() if q.is_held_out]
    assert len(held) == 3 and len(questions) - len(held) == 6


def test_every_question_has_human_answer(questions, humans):
    assert set(questions) == set(humans)


def test_held_out_twins_share_family_id(questions):
    """Each held-out question shares its family_id with exactly one train question."""
    for q in questions.values():
        if q.is_held_out:
            twins = [o for o in questions.values()
                     if o.family_id == q.family_id and not o.is_held_out]
            assert len(twins) == 1, f"{q.id} has no unique train twin"


def test_gold_evidence_exists_and_excludes_distractors(evidence, humans):
    for h in humans.values():
        assert h.key_source_ids, f"{h.question_id} has no gold evidence"
        for sid in h.key_source_ids:
            assert sid in evidence, f"{h.question_id}: gold id {sid} not in corpus"
            assert sid not in DISTRACTORS, f"{h.question_id}: gold id {sid} is a distractor!"


def test_every_question_has_rubric(humans):
    for h in humans.values():
        assert 3 <= len(h.root_cause_rubric) <= 5, f"{h.question_id} rubric size"
        assert h.root_causes


def test_p2_chain_present(evidence):
    """The crucial P2 root-cause commit and its revert must exist."""
    for sid in ("commit:a1", "commit:a15", "ticket:RISK-220", "slack:inc-jun3-charge"):
        assert sid in evidence


def test_pay540_does_not_leak_mechanism(evidence):
    """Regression: the fix ticket must not state the disabled-idempotency mechanism;
    that belongs only to commits a1/a15 (so V1 can't get rubric RC2 for free)."""
    pay540 = evidence["ticket:PAY-540"]
    text = f"{pay540.title}\n{pay540.body}".lower()
    assert "idempotency" not in text
    # the mechanism wording lives in the commits instead
    assert "idempotency" in evidence["commit:a1"].title.lower()
