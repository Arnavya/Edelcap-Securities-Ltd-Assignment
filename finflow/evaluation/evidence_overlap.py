"""Deterministic evidence-coverage scoring (recall is primary)."""

from __future__ import annotations

from ..models import EvidenceOverlapResult


def compute_overlap(cited: list[str], gold: list[str]) -> EvidenceOverlapResult:
    cited_set, gold_set = set(cited), set(gold)
    matched = cited_set & gold_set
    recall = len(matched) / len(gold_set) if gold_set else 0.0
    precision = len(matched) / len(cited_set) if cited_set else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return EvidenceOverlapResult(
        recall=round(recall, 4),
        precision=round(precision, 4),
        f1=round(f1, 4),
        matched_ids=sorted(matched),
        missed_ids=sorted(gold_set - cited_set),
    )
