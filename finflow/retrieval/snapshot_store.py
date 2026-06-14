"""Persist retrieval snapshots as JSON for replay and dashboard display.

Lightweight on purpose: one JSON file per (question, version). The SQLite
repository (later phase) can also store these, but a file store keeps retrieval
debuggable in isolation and lets P6/P7 diff V1 vs V2 retrieval offline.
"""

from __future__ import annotations

from pathlib import Path

from ..models import RetrievalSnapshot

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "retrieval_snapshots"


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def snapshot_path(snapshot: RetrievalSnapshot, directory: Path | None = None) -> Path:
    directory = directory or DEFAULT_DIR
    qid = _safe(snapshot.question_id or "adhoc")
    ver = _safe(snapshot.version or "V1")
    return directory / f"{qid}__{ver}.json"


def save_snapshot(snapshot: RetrievalSnapshot, directory: Path | None = None) -> Path:
    directory = directory or DEFAULT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(snapshot, directory)
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_snapshot(path: Path) -> RetrievalSnapshot:
    return RetrievalSnapshot.model_validate_json(Path(path).read_text(encoding="utf-8"))
