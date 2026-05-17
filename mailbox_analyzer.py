"""Mailbox analysis for deriving a compact folder structure from real mail."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TopicDefinition:
    """A deliberately broad topic bucket."""

    key: str
    label: str
    folder_path: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class TopicSummary:
    """Aggregated evidence for one topic."""

    label: str
    folder_path: str
    message_count: int
    unique_sender_count: int
    example_senders: tuple[str, ...]
    example_subjects: tuple[str, ...]


TOPICS: tuple[TopicDefinition, ...] = (
    TopicDefinition(
        key="orders",
        label="Bestellungen & Käufe",
        folder_path="Finanzen/Bestellungen",
        keywords=(
            "amazon",
            "ebay",
            "paypal",
            "klarna",
            "bestellung",
            "your order",
            "order confirmed",
            "order confirmation",
            "versand",
            "shipping",
        ),
    ),
    TopicDefinition(
        key="invoices",
        label="Rechnungen & Zahlungen",
        folder_path="Finanzen/Rechnungen",
        keywords=(
            "rechnung",
            "invoice",
            "beleg",
            "zahlungsbestätigung",
            "payment confirmation",
            "abbuchung",
            "kontoauszug",
        ),
    ),
    TopicDefinition(
        key="newsletters",
        label="Newsletter",
        folder_path="Newsletter",
        keywords=(
            "unsubscribe",
            "abmelden",
            "newsletter",
        ),
    ),
    TopicDefinition(
        key="travel",
        label="Reisen",
        folder_path="Reisen",
        keywords=(
            "booking",
            "buchung",
            "flug",
            "flight",
            "hotel",
            "bahn",
            "ticket",
            "reise",
        ),
    ),
    TopicDefinition(
        key="accounts",
        label="Konten & Sicherheit",
        folder_path="Konten & Sicherheit",
        keywords=(
            "passwort",
            "password",
            "security",
            "sicherheitscode",
            "anmeldecode",
            "verification code",
            "bestätigungscode",
            "neue anmeldung",
            "neues gerät",
            "neue apps wurden",
            "passwort zurücksetzen",
        ),
    ),
    TopicDefinition(
        key="contracts",
        label="Verträge & Rechtliches",
        folder_path="Dokumente/Rechtliches",
        keywords=(
            "vertrag",
            "agb",
            "datenschutz",
            "impressum",
            "kündigung",
        ),
    ),
    TopicDefinition(
        key="tools",
        label="Tools & Dienste",
        folder_path="Tools & Dienste",
        keywords=(
            "openai",
            "microsoft",
            "github",
            "framer",
            "notion",
            "figma",
        ),
    ),
)

TOPICS_BY_FOLDER_PATH = {topic.folder_path: topic for topic in TOPICS}


def _normalize(value: str | None) -> str:
    return (value or "").casefold()


def _sender_text(message: dict[str, Any]) -> str:
    sender = message.get("sender") or {}
    email_address = sender.get("emailAddress") or {}
    name = email_address.get("name") or ""
    address = email_address.get("address") or ""
    return f"{name} {address}".strip()


def _sender_address(message: dict[str, Any]) -> str:
    sender = message.get("sender") or {}
    email_address = sender.get("emailAddress") or {}
    return email_address.get("address") or "unbekannt"


def _haystack(message: dict[str, Any]) -> str:
    return " ".join(
        (
            _normalize(_sender_text(message)),
            _normalize(message.get("subject")),
            _normalize(message.get("bodyPreview")),
        )
    )


def _subject_sender_text(message: dict[str, Any]) -> str:
    return " ".join(
        (
            _normalize(_sender_text(message)),
            _normalize(message.get("subject")),
        )
    )


def _matches_topic(message: dict[str, Any], topic: TopicDefinition) -> bool:
    """
    Match only against the evidence that is actually trustworthy per topic.

    Body previews are noisy and often contain footers or unrelated wording.
    They are useful for newsletters, but too permissive for archival moves.
    """
    subject_sender = _subject_sender_text(message)
    full_text = _haystack(message)

    if topic.key == "newsletters":
        return any(keyword in full_text for keyword in topic.keywords)

    return any(keyword in subject_sender for keyword in topic.keywords)


def _matching_topic(message: dict[str, Any]) -> TopicDefinition | None:
    return next(
        (
            topic
            for topic in TOPICS
            if _matches_topic(message, topic)
        ),
        None,
    )


def analyze_mailbox(
    messages: list[dict[str, Any]],
    min_messages_per_topic: int,
) -> tuple[list[TopicSummary], int]:
    """
    Analyze recent mailbox history and return only stable folder candidates.

    A topic must appear often enough before it becomes a recommendation.
    """
    grouped_messages: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unclassified_count = 0

    for message in messages:
        topic = _matching_topic(message)
        if topic is None:
            unclassified_count += 1
            continue
        grouped_messages[topic.key].append(message)

    summaries: list[TopicSummary] = []
    topics_by_key = {topic.key: topic for topic in TOPICS}

    for topic_key, topic_messages in grouped_messages.items():
        if len(topic_messages) < min_messages_per_topic:
            continue

        topic = topics_by_key[topic_key]
        sender_counter = Counter(_sender_address(message) for message in topic_messages)
        example_senders = tuple(sender for sender, _ in sender_counter.most_common(3))
        example_subjects = tuple(
            message.get("subject") or "(ohne Betreff)"
            for message in topic_messages[:3]
        )
        summaries.append(
            TopicSummary(
                label=topic.label,
                folder_path=topic.folder_path,
                message_count=len(topic_messages),
                unique_sender_count=len(sender_counter),
                example_senders=example_senders,
                example_subjects=example_subjects,
            )
        )

    summaries.sort(
        key=lambda summary: (-summary.message_count, summary.folder_path.casefold())
    )
    return summaries, unclassified_count


def stable_topic_paths(summaries: list[TopicSummary]) -> set[str]:
    """Return the folder paths that are stable enough for automatic use."""
    return {summary.folder_path for summary in summaries}


def suggest_stable_topic_folder(
    message: dict[str, Any],
    allowed_paths: set[str],
) -> str | None:
    """
    Suggest a folder only when the topic is stable in this mailbox.

    This keeps automatic behavior tied to real mailbox evidence instead of
    inventing new structure from a one-off message.
    """
    topic = _matching_topic(message)
    if topic and topic.folder_path in allowed_paths:
        return topic.folder_path
    return None
