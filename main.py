"""Entry point for the safe read-only Outlook sorter."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from typing import Any

from auth import get_access_token
from config import (
    ANALYSIS_MESSAGE_LIMIT,
    BACKFILL_MESSAGE_LIMIT,
    CREATE_MISSING_FOLDERS,
    DEFAULT_MODE,
    LOG_DIR,
    MESSAGE_LIMIT,
    MIN_MESSAGES_PER_TOPIC,
    MIN_RUNS_FOR_STABLE_TOPIC,
    MIN_TARGET_MESSAGES_TO_CREATE_FOLDER,
    MIN_TOTAL_MESSAGES_FOR_STABLE_TOPIC,
    MAX_RUNS_SINCE_LAST_SEEN_FOR_STABLE_TOPIC,
    MIN_UNIQUE_SENDERS_FOR_STABLE_TOPIC,
    STRONG_TOPIC_MESSAGE_THRESHOLD,
    STRONG_TOPIC_UNIQUE_SENDERS_THRESHOLD,
    MOVE_MESSAGES,
    TOPIC_MEMORY_FILE,
)
from folder_resolver import FolderCreationResult, FolderResolution, FolderResolver
from graph_client import GraphClient
from mailbox_analyzer import TopicSummary, analyze_mailbox
from rules import KEEP_IN_INBOX, suggest_target_folder
from run_logger import RunLog, write_run_log
from topic_memory import (
    load_topic_memory,
    save_topic_memory,
    stable_paths_from_memory,
    update_topic_memory,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lokaler Outlook-Mail-Sortierer für private Konten.",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("preview", "apply", "backfill-preview", "backfill-apply"),
        default=DEFAULT_MODE,
        help=(
            "preview/apply = täglicher Lauf, "
            "backfill-preview/backfill-apply = größerer Einmallauf für Bestand"
        ),
    )
    return parser.parse_args()


def _configure_console_output() -> None:
    """Prefer UTF-8 output on Windows terminals when supported."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _format_sender(message: dict[str, Any]) -> str:
    sender = message.get("sender") or {}
    email_address = sender.get("emailAddress") or {}
    name = email_address.get("name") or "Unbekannter Absender"
    address = email_address.get("address") or "keine Adresse"
    return f"{name} <{address}>"


def _format_received_date(value: str | None) -> str:
    if not value:
        return "unbekannt"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


def _shorten(text: str | None, max_length: int = 140) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 1].rstrip() + "…"


def _print_login_success() -> None:
    print("\nLogin erfolgreich.")


def _print_account_info(me: dict[str, Any]) -> None:
    display_name = me.get("displayName") or "Unbekannt"
    email = me.get("mail") or me.get("userPrincipalName") or "Unbekannt"
    print("\nKonto-Test")
    print(f"Name: {display_name}")
    print(f"Mailadresse: {email}")


def _print_folders(folders: list[dict[str, Any]]) -> None:
    print("\nTop-Level-Mailordner")
    if not folders:
        print("- Keine Ordner gefunden.")
        return

    for folder in folders:
        name = folder.get("displayName") or "Ohne Namen"
        total = folder.get("totalItemCount", "?")
        unread = folder.get("unreadItemCount", "?")
        print(f"- {name} (gesamt: {total}, ungelesen: {unread})")


def _print_mailbox_analysis(
    summaries: list[TopicSummary],
    sample_size: int,
    unclassified_count: int,
    long_term_stable_paths: set[str],
) -> None:
    print("\nPostfach-Analyse im Dry-Run")
    print(
        f"- Analysiert: {sample_size} aktuelle Mail(s) "
        f"(Themen-Schwelle: mindestens {MIN_MESSAGES_PER_TOPIC})."
    )

    if not summaries:
        print("- Noch keine stabilen Themen stark genug für neue Ordnerempfehlungen.")
    else:
        print("- Empfohlene kompakte Struktur aus wiederkehrenden Mustern:")
        for summary in summaries:
            senders = ", ".join(summary.example_senders)
            print(
                f"  • {summary.folder_path} "
                f"({summary.message_count} Mail(s), "
                f"{summary.unique_sender_count} Absender; Beispiele: {senders})"
            )

    print(
        f"- Bewusst nicht einsortiert: {unclassified_count} Mail(s), "
        "damit Einzelthemen nicht sofort neue Ordner erzeugen."
    )
    if long_term_stable_paths:
        print("- Langfristig stabile Themen:")
        for path in sorted(long_term_stable_paths):
            print(f"  • {path}")
    else:
        print("- Noch keine Themen langfristig stabil über mehrere Läufe.")


def _build_target_counts(
    messages: list[dict[str, Any]],
    allowed_paths: set[str],
) -> Counter[str]:
    return Counter(
        suggest_target_folder(message, allowed_paths)
        for message in messages
        if suggest_target_folder(message, allowed_paths) != KEEP_IN_INBOX
    )


def _build_inbox_decisions(
    messages: list[dict[str, Any]],
    allowed_paths: set[str],
) -> list[dict[str, Any]]:
    return [
        {
            "message_id": message.get("id"),
            "sender": _format_sender(message),
            "subject": message.get("subject") or "(ohne Betreff)",
            "received": message.get("receivedDateTime"),
            "suggested_folder": suggest_target_folder(message, allowed_paths),
        }
        for message in messages
    ]


def _print_messages(messages: list[dict[str, Any]], allowed_paths: set[str]) -> None:
    print(f"\nPosteingang - letzte {len(messages)} Mail(s)")
    if not messages:
        print("- Keine Nachrichten gefunden.")
        return

    for index, message in enumerate(messages, start=1):
        print(f"\n[{index}]")
        print(f"Absender: {_format_sender(message)}")
        print(f"Betreff: {message.get('subject') or '(ohne Betreff)'}")
        print(f"Empfangen: {_format_received_date(message.get('receivedDateTime'))}")
        print(f"Vorschau: {_shorten(message.get('bodyPreview'))}")
        target = suggest_target_folder(message, allowed_paths)
        if target == KEEP_IN_INBOX:
            print("Vorschlag: Im Posteingang lassen")
        else:
            print(f"Vorschlag: {target}")


def _build_resolution_map(
    resolutions: list[FolderResolution],
) -> dict[str, FolderResolution]:
    return {resolution.path: resolution for resolution in resolutions}


def _print_folder_plan(
    resolutions: list[FolderResolution],
    target_counts: Counter[str],
) -> None:
    print("\nOrdner-Check im Dry-Run")
    if not resolutions:
        print("- Keine Zielordner zu prüfen.")
        return

    for resolution in resolutions:
        message_count = target_counts[resolution.path]
        if resolution.exists:
            print(
                f"- OK: {resolution.path} existiert bereits "
                f"({message_count} vorgeschlagene Mail(s))."
            )
            continue

        if resolution.existing_path:
            print(
                f"- FEHLT TEILWEISE: {resolution.path} "
                f"(vorhanden: {resolution.existing_path}; "
                f"später anzulegen: {resolution.missing_path}; "
                f"{message_count} vorgeschlagene Mail(s))."
            )
        else:
            print(
                f"- FEHLT: {resolution.path} "
                f"(später anzulegen: {resolution.missing_path}; "
                f"{message_count} vorgeschlagene Mail(s))."
            )


def _create_missing_folders_if_enabled(
    resolver: FolderResolver,
    resolutions: list[FolderResolution],
    target_counts: Counter[str],
    allowed_paths: set[str],
    is_preview: bool,
) -> list[FolderCreationResult]:
    missing = [
        resolution
        for resolution in resolutions
        if (
            not resolution.exists
            and resolution.path in allowed_paths
            and target_counts[resolution.path] >= MIN_TARGET_MESSAGES_TO_CREATE_FOLDER
        )
    ]
    blocked = [
        resolution
        for resolution in resolutions
        if not resolution.exists and resolution not in missing
    ]
    if not missing:
        print("\nKeine anlagef?higen fehlenden Zielordner.")
        for resolution in blocked:
            if resolution.path not in allowed_paths:
                print(
                    f"- Nicht angelegt, weil Thema noch nicht stabil genug ist: "
                    f"{resolution.path}"
                )
            else:
                print(
                    f"- Nicht angelegt, weil im aktuellen Lauf erst "
                    f"{target_counts[resolution.path]} passende Mail(s) vorliegen: "
                    f"{resolution.path}"
                )
        return []

    print("\nOrdner-Anlage")
    if is_preview:
        print("- Deaktiviert, weil Modus = preview.")
        return []

    if not CREATE_MISSING_FOLDERS:
        print("- Deaktiviert, weil CREATE_MISSING_FOLDERS = False.")
        return []

    results = [resolver.ensure_exists(resolution.path) for resolution in missing]
    for result in results:
        for created_path in result.created_paths:
            print(f"- Angelegt: {created_path}")
    for resolution in blocked:
        if resolution.path not in allowed_paths:
            print(
                f"- Nicht angelegt, weil Thema noch nicht stabil genug ist: "
                f"{resolution.path}"
            )
        else:
            print(
                f"- Nicht angelegt, weil im aktuellen Lauf erst "
                f"{target_counts[resolution.path]} passende Mail(s) vorliegen: "
                f"{resolution.path}"
            )
    return results


def _refresh_resolutions_after_creation(
    resolver: FolderResolver,
    target_counts: Counter[str],
) -> list[FolderResolution]:
    return [resolver.resolve(path) for path in sorted(target_counts)]


def _print_move_plan(
    messages: list[dict[str, Any]],
    resolution_map: dict[str, FolderResolution],
    allowed_paths: set[str],
) -> None:
    print("\nVerschiebe-Plan")
    if not messages:
        print("- Keine Nachrichten zu prüfen.")
        return

    for index, message in enumerate(messages, start=1):
        target_path = suggest_target_folder(message, allowed_paths)
        if target_path == KEEP_IN_INBOX:
            subject = message.get("subject") or "(ohne Betreff)"
            print(f"- [{index}] bleibt im Posteingang: {subject}")
            continue
        resolution = resolution_map[target_path]
        subject = message.get("subject") or "(ohne Betreff)"
        if resolution.exists:
            print(f"- [{index}] würde verschoben nach {target_path}: {subject}")
        else:
            print(
                f"- [{index}] NICHT verschiebbar, Ziel fehlt ({target_path}): {subject}"
            )


def _move_messages_if_enabled(
    graph: GraphClient,
    messages: list[dict[str, Any]],
    resolution_map: dict[str, FolderResolution],
    allowed_paths: set[str],
    is_preview: bool,
) -> list[dict[str, Any]]:
    movable = [
        (message, resolution_map[suggest_target_folder(message, allowed_paths)])
        for message in messages
        if suggest_target_folder(message, allowed_paths) != KEEP_IN_INBOX
        if resolution_map[suggest_target_folder(message, allowed_paths)].exists
    ]

    print("\nMail-Verschiebung")
    if is_preview:
        print("- Deaktiviert, weil Modus = preview.")
        return []

    if not MOVE_MESSAGES:
        print("- Deaktiviert, weil MOVE_MESSAGES = False.")
        return []

    if not movable:
        print("- Keine Mails mit aufgelöstem Zielordner gefunden.")
        return []

    moved_messages: list[dict[str, Any]] = []
    for message, resolution in movable:
        message_id = message.get("id")
        if not message_id or not resolution.resolved_folder_id:
            continue
        graph.move_message(message_id, resolution.resolved_folder_id)
        subject = message.get("subject") or "(ohne Betreff)"
        print(f"- Verschoben nach {resolution.path}: {subject}")
        moved_messages.append(
            {
                "message_id": message_id,
                "subject": subject,
                "destination": resolution.path,
            }
        )

    return moved_messages


def _folder_resolution_to_dict(resolution: FolderResolution) -> dict[str, Any]:
    return {
        "path": resolution.path,
        "exists": resolution.exists,
        "existing_path": resolution.existing_path,
        "missing_path": resolution.missing_path,
    }


def _topic_summary_to_dict(summary: TopicSummary) -> dict[str, Any]:
    return {
        "label": summary.label,
        "folder_path": summary.folder_path,
        "message_count": summary.message_count,
        "unique_sender_count": summary.unique_sender_count,
        "example_senders": list(summary.example_senders),
    }


def main() -> None:
    _configure_console_output()
    args = _parse_args()
    is_preview = args.mode in {"preview", "backfill-preview"}
    is_backfill = args.mode in {"backfill-preview", "backfill-apply"}

    print("Outlook Mail-Sortierer - Version 15")
    if is_preview:
        print("DRY RUN AKTIV - Es werden keine Mails verändert.")
    else:
        print("APPLY-MODUS AKTIV - Schreibzugriffe sind nur mit weiteren Schaltern möglich.")

    access_token = get_access_token()
    _print_login_success()

    graph = GraphClient(access_token)
    me = graph.get_me()
    folders = graph.list_top_level_mail_folders()
    messages = (
        graph.list_recent_inbox_messages(BACKFILL_MESSAGE_LIMIT)
        if is_backfill
        else graph.list_inbox_messages(MESSAGE_LIMIT)
    )
    analysis_messages = graph.list_recent_messages(ANALYSIS_MESSAGE_LIMIT)
    topic_summaries, unclassified_count = analyze_mailbox(
        analysis_messages,
        MIN_MESSAGES_PER_TOPIC,
    )
    topic_memory = load_topic_memory(TOPIC_MEMORY_FILE)
    topic_memory = update_topic_memory(topic_memory, topic_summaries)
    save_topic_memory(TOPIC_MEMORY_FILE, topic_memory)
    allowed_paths = stable_paths_from_memory(
        topic_memory,
        MIN_RUNS_FOR_STABLE_TOPIC,
        MIN_TOTAL_MESSAGES_FOR_STABLE_TOPIC,
        MAX_RUNS_SINCE_LAST_SEEN_FOR_STABLE_TOPIC,
        MIN_UNIQUE_SENDERS_FOR_STABLE_TOPIC,
        STRONG_TOPIC_MESSAGE_THRESHOLD,
        STRONG_TOPIC_UNIQUE_SENDERS_THRESHOLD,
    )
    target_counts = _build_target_counts(messages, allowed_paths)
    inbox_decisions = _build_inbox_decisions(messages, allowed_paths)
    resolver = FolderResolver(graph, folders)
    resolutions = [
        resolver.resolve(path)
        for path in sorted(target_counts)
    ]

    _print_account_info(me)
    _print_folders(folders)
    _print_mailbox_analysis(
        topic_summaries,
        len(analysis_messages),
        unclassified_count,
        allowed_paths,
    )
    _print_messages(messages, allowed_paths)
    _print_folder_plan(resolutions, target_counts)
    creation_results = _create_missing_folders_if_enabled(
        resolver,
        resolutions,
        target_counts,
        allowed_paths,
        is_preview,
    )
    if creation_results:
        resolutions = _refresh_resolutions_after_creation(resolver, target_counts)

    resolution_map = _build_resolution_map(resolutions)
    _print_move_plan(messages, resolution_map, allowed_paths)
    moved_messages = _move_messages_if_enabled(
        graph,
        messages,
        resolution_map,
        allowed_paths,
        is_preview,
    )

    blocked_folder_creations = [
        resolution.path
        for resolution in resolutions
        if (
            not resolution.exists
            and (
                resolution.path not in allowed_paths
                or target_counts[resolution.path] < MIN_TARGET_MESSAGES_TO_CREATE_FOLDER
            )
        )
    ]
    created_folders = [
        created_path
        for result in creation_results
        for created_path in result.created_paths
    ]
    run_log = RunLog(
        mode=args.mode,
        analyzed_messages=len(analysis_messages),
        stable_topics=[_topic_summary_to_dict(summary) for summary in topic_summaries],
        inbox_decisions=inbox_decisions,
        folder_resolutions=[
            _folder_resolution_to_dict(resolution) for resolution in resolutions
        ],
        created_folders=created_folders,
        blocked_folder_creations=blocked_folder_creations,
        moved_messages=moved_messages,
    )
    log_path = write_run_log(LOG_DIR, run_log)
    print(f"\nProtokoll gespeichert: {log_path}")

    if moved_messages:
        print(
            f"\nFertig. {len(moved_messages)} Mail(s) wurden verschoben. "
            "Es wurde nichts gelöscht."
        )
    elif creation_results:
        print("\nFertig. Es wurden keine Mails verschoben oder gelöscht.")
    else:
        print("\nFertig. Es wurden keine Mails verschoben, gelöscht oder verändert.")


if __name__ == "__main__":
    main()
