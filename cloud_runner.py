"""Cloud-oriented wrapper around the existing sorter workflow."""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from config import (
    ANALYSIS_MESSAGE_LIMIT,
    CREATE_MISSING_FOLDERS,
    MAX_RUNS_SINCE_LAST_SEEN_FOR_STABLE_TOPIC,
    MESSAGE_LIMIT,
    MIN_MESSAGES_PER_TOPIC,
    MIN_RUNS_FOR_STABLE_TOPIC,
    MIN_TARGET_MESSAGES_TO_CREATE_FOLDER,
    MIN_TOTAL_MESSAGES_FOR_STABLE_TOPIC,
    MIN_UNIQUE_SENDERS_FOR_STABLE_TOPIC,
    MOVE_MESSAGES,
    STRONG_TOPIC_MESSAGE_THRESHOLD,
    STRONG_TOPIC_UNIQUE_SENDERS_THRESHOLD,
)
from folder_resolver import FolderResolver
from mailbox_analyzer import analyze_mailbox
from rules import KEEP_IN_INBOX, suggest_target_folder
from run_logger import RunLog
from state_store import StateStore
from topic_memory import stable_paths_from_memory, update_topic_memory


def _target_counts(messages: list[dict[str, Any]], allowed_paths: set[str]) -> Counter[str]:
    return Counter(
        target
        for message in messages
        if (target := suggest_target_folder(message, allowed_paths)) != KEEP_IN_INBOX
    )


def run_cloud_sorter(
    graph,
    store: StateStore,
    load_memory: Callable[[str | None], dict],
    dump_memory: Callable[[dict], str],
) -> dict[str, Any]:
    """Run the sorter without console output for Azure Functions."""
    folders = graph.list_top_level_mail_folders()
    messages = graph.list_inbox_messages(MESSAGE_LIMIT)
    analysis_messages = graph.list_recent_messages(ANALYSIS_MESSAGE_LIMIT)
    topic_summaries, unclassified_count = analyze_mailbox(
        analysis_messages,
        MIN_MESSAGES_PER_TOPIC,
    )

    memory = load_memory(store.read_text("topic_memory.json"))
    memory = update_topic_memory(memory, topic_summaries)
    store.write_text("topic_memory.json", dump_memory(memory))
    allowed_paths = stable_paths_from_memory(
        memory,
        MIN_RUNS_FOR_STABLE_TOPIC,
        MIN_TOTAL_MESSAGES_FOR_STABLE_TOPIC,
        MAX_RUNS_SINCE_LAST_SEEN_FOR_STABLE_TOPIC,
        MIN_UNIQUE_SENDERS_FOR_STABLE_TOPIC,
        STRONG_TOPIC_MESSAGE_THRESHOLD,
        STRONG_TOPIC_UNIQUE_SENDERS_THRESHOLD,
    )

    target_counts = _target_counts(messages, allowed_paths)
    resolver = FolderResolver(graph, folders)
    resolutions = [resolver.resolve(path) for path in sorted(target_counts)]

    creation_results = []
    if CREATE_MISSING_FOLDERS:
        creation_results = [
            resolver.ensure_exists(resolution.path)
            for resolution in resolutions
            if (
                not resolution.exists
                and resolution.path in allowed_paths
                and target_counts[resolution.path] >= MIN_TARGET_MESSAGES_TO_CREATE_FOLDER
            )
        ]
        if creation_results:
            resolutions = [resolver.resolve(path) for path in sorted(target_counts)]

    resolution_map = {resolution.path: resolution for resolution in resolutions}
    moved_messages = []
    if MOVE_MESSAGES:
        for message in messages:
            target = suggest_target_folder(message, allowed_paths)
            if target == KEEP_IN_INBOX:
                continue
            resolution = resolution_map[target]
            if not resolution.exists or not resolution.resolved_folder_id:
                continue
            message_id = message.get("id")
            if not message_id:
                continue
            graph.move_message(message_id, resolution.resolved_folder_id)
            moved_messages.append(
                {
                    "message_id": message_id,
                    "subject": message.get("subject") or "(ohne Betreff)",
                    "destination": target,
                }
            )

    run_log = RunLog(
        mode="apply",
        analyzed_messages=len(analysis_messages),
        stable_topics=[
            {
                "label": summary.label,
                "folder_path": summary.folder_path,
                "message_count": summary.message_count,
                "unique_sender_count": summary.unique_sender_count,
                "example_senders": list(summary.example_senders),
            }
            for summary in topic_summaries
        ],
        inbox_decisions=[
            {
                "message_id": message.get("id"),
                "subject": message.get("subject") or "(ohne Betreff)",
                "suggested_folder": suggest_target_folder(message, allowed_paths),
            }
            for message in messages
        ],
        folder_resolutions=[
            {
                "path": resolution.path,
                "exists": resolution.exists,
                "existing_path": resolution.existing_path,
                "missing_path": resolution.missing_path,
            }
            for resolution in resolutions
        ],
        created_folders=[
            created_path
            for result in creation_results
            for created_path in result.created_paths
        ],
        blocked_folder_creations=[
            resolution.path
            for resolution in resolutions
            if (
                not resolution.exists
                and (
                    resolution.path not in allowed_paths
                    or target_counts[resolution.path] < MIN_TARGET_MESSAGES_TO_CREATE_FOLDER
                )
            )
        ],
        moved_messages=moved_messages,
    )
    return {
        "run_log": run_log,
        "moved_messages": moved_messages,
        "unclassified_count": unclassified_count,
    }
