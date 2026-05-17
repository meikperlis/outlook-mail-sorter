"""Persistent lightweight memory for topic stability across runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from mailbox_analyzer import TopicSummary


@dataclass
class TopicMemoryEntry:
    """Aggregated topic evidence across runs."""

    folder_path: str
    label: str
    total_messages_seen: int = 0
    runs_seen: int = 0
    runs_since_last_seen: int = 0
    sender_addresses: list[str] | None = None


def load_topic_memory(path: Path) -> dict[str, TopicMemoryEntry]:
    """Load persisted topic memory if it exists."""
    if not path.exists():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        folder_path: TopicMemoryEntry(**entry)
        for folder_path, entry in raw.items()
    }


def load_topic_memory_from_text(raw_text: str | None) -> dict[str, TopicMemoryEntry]:
    if not raw_text:
        return {}
    raw = json.loads(raw_text)
    return {
        folder_path: TopicMemoryEntry(**entry)
        for folder_path, entry in raw.items()
    }


def update_topic_memory(
    memory: dict[str, TopicMemoryEntry],
    summaries: list[TopicSummary],
) -> dict[str, TopicMemoryEntry]:
    """Merge the latest run into long-term topic memory."""
    seen_paths = {summary.folder_path for summary in summaries}

    for entry in memory.values():
        if entry.folder_path in seen_paths:
            continue
        entry.runs_since_last_seen += 1

    for summary in summaries:
        entry = memory.get(summary.folder_path)
        if entry is None:
            entry = TopicMemoryEntry(
                folder_path=summary.folder_path,
                label=summary.label,
            )
            memory[summary.folder_path] = entry
        entry.total_messages_seen += summary.message_count
        entry.runs_seen += 1
        entry.runs_since_last_seen = 0
        existing_senders = set(entry.sender_addresses or [])
        existing_senders.update(summary.example_senders)
        entry.sender_addresses = sorted(existing_senders)
    return memory


def stable_paths_from_memory(
    memory: dict[str, TopicMemoryEntry],
    min_runs: int,
    min_total_messages: int,
    max_runs_since_last_seen: int,
    min_unique_senders: int,
    strong_topic_message_threshold: int,
    strong_topic_unique_senders_threshold: int,
) -> set[str]:
    """Return topics that proved themselves across time, not just once."""
    stable_paths: set[str] = set()
    for entry in memory.values():
        unique_senders = len(entry.sender_addresses or [])
        is_long_term_stable = (
            entry.runs_seen >= min_runs
            and entry.total_messages_seen >= min_total_messages
            and entry.runs_since_last_seen <= max_runs_since_last_seen
            and unique_senders >= min_unique_senders
        )
        is_strong_immediate_topic = (
            entry.total_messages_seen >= strong_topic_message_threshold
            and unique_senders >= strong_topic_unique_senders_threshold
            and entry.runs_since_last_seen == 0
        )
        if is_long_term_stable or is_strong_immediate_topic:
            stable_paths.add(entry.folder_path)
    return stable_paths


def save_topic_memory(path: Path, memory: dict[str, TopicMemoryEntry]) -> None:
    """Persist long-term memory to disk."""
    serialized = {
        folder_path: asdict(entry)
        for folder_path, entry in sorted(memory.items())
    }
    path.write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_topic_memory_to_text(memory: dict[str, TopicMemoryEntry]) -> str:
    serialized = {
        folder_path: asdict(entry)
        for folder_path, entry in sorted(memory.items())
    }
    return json.dumps(serialized, ensure_ascii=False, indent=2)
