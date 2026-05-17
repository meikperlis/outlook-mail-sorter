"""Small JSON run log for traceable sorter decisions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from state_store import StateStore


@dataclass
class RunLog:
    """Structured log for one sorter run."""

    mode: str
    analyzed_messages: int
    stable_topics: list[dict[str, Any]] = field(default_factory=list)
    inbox_decisions: list[dict[str, Any]] = field(default_factory=list)
    folder_resolutions: list[dict[str, Any]] = field(default_factory=list)
    created_folders: list[str] = field(default_factory=list)
    blocked_folder_creations: list[str] = field(default_factory=list)
    moved_messages: list[dict[str, Any]] = field(default_factory=list)
    created_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def write_run_log(log_dir: Path, run_log: RunLog) -> Path:
    """Persist one JSON file and return its path."""
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = log_dir / f"run_{timestamp}.json"
    path.write_text(
        json.dumps(asdict(run_log), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def write_run_log_to_store(store: StateStore, run_log: RunLog) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"logs/run_{timestamp}.json"
    store.write_text(
        name,
        json.dumps(asdict(run_log), ensure_ascii=False, indent=2),
    )
    return name
