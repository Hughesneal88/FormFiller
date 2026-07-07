"""Persist and retrieve submission records for review."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUBMISSIONS_DIR = Path(__file__).resolve().parent.parent / "submissions"
SUBMISSIONS_DIR.mkdir(exist_ok=True)


def _batch_dir(batch_id: str) -> Path:
    return SUBMISSIONS_DIR / batch_id


def create_batch(count: int, *, submit: bool) -> str:
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_path = _batch_dir(batch_id)
    batch_path.mkdir(parents=True)
    meta = {
        "batch_id": batch_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "planned_count": count,
        "submit_enabled": submit,
        "completed": 0,
        "status": "running",
    }
    (batch_path / "batch.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return batch_id


def save_submission(
    batch_id: str,
    respondent: int,
    *,
    answers: dict[str, Any],
    status: str,
    fields_filled: int,
    screenshot_path: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    batch_path = _batch_dir(batch_id)
    batch_path.mkdir(parents=True, exist_ok=True)

    record = {
        "respondent": respondent,
        "batch_id": batch_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "fields_filled": fields_filled,
        "answers": {k: v for k, v in answers.items() if not k.startswith("_")},
        "meta": answers.get("_meta", {}),
        "screenshot": screenshot_path,
        "error": error,
    }

    out = batch_path / f"respondent_{respondent:03d}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    meta_path = batch_path / "batch.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["completed"] = meta.get("completed", 0) + 1
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return record


def finish_batch(batch_id: str, results: list[dict[str, Any]]) -> None:
    meta_path = _batch_dir(batch_id) / "batch.json"
    if not meta_path.exists():
        return
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status"] = "complete"
    meta["completed"] = len(results)
    meta["finished_at"] = datetime.now(timezone.utc).isoformat()
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def list_batches() -> list[dict[str, Any]]:
    batches = []
    for path in sorted(SUBMISSIONS_DIR.iterdir(), reverse=True):
        if not path.is_dir():
            continue
        meta_file = path / "batch.json"
        if meta_file.exists():
            batches.append(json.loads(meta_file.read_text(encoding="utf-8")))
        else:
            files = list(path.glob("respondent_*.json"))
            batches.append({
                "batch_id": path.name,
                "completed": len(files),
                "status": "unknown",
            })
    return batches


def get_batch(batch_id: str) -> dict[str, Any] | None:
    batch_path = _batch_dir(batch_id)
    if not batch_path.exists():
        return None

    meta = {}
    meta_file = batch_path / "batch.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text(encoding="utf-8"))

    submissions = []
    for f in sorted(batch_path.glob("respondent_*.json")):
        submissions.append(json.loads(f.read_text(encoding="utf-8")))

    return {**meta, "submissions": submissions}


def get_submission(batch_id: str, respondent: int) -> dict[str, Any] | None:
    path = _batch_dir(batch_id) / f"respondent_{respondent:03d}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def screenshot_path(batch_id: str, respondent: int) -> Path | None:
    batch_path = _batch_dir(batch_id)
    for pattern in [f"respondent_{respondent:03d}.png", f"respondent_{respondent}.png"]:
        p = batch_path / pattern
        if p.exists():
            return p
    return None
