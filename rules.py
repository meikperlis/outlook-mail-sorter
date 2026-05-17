"""Simple deterministic categorization rules for dry-run suggestions."""

from __future__ import annotations

from typing import Any

KEEP_IN_INBOX = "Posteingang"


def _normalize(value: str | None) -> str:
    return (value or "").casefold()


def _extract_sender_text(message: dict[str, Any]) -> str:
    sender = message.get("sender") or {}
    email_address = sender.get("emailAddress") or {}
    name = email_address.get("name") or ""
    address = email_address.get("address") or ""
    return f"{name} {address}".strip()


def suggest_target_folder(
    message: dict[str, Any],
    stable_topic_paths: set[str] | None = None,
) -> str:
    """Return a deterministic target-folder suggestion for one message."""
    if stable_topic_paths is not None:
        from mailbox_analyzer import suggest_stable_topic_folder

        stable_suggestion = suggest_stable_topic_folder(message, stable_topic_paths)
        if stable_suggestion:
            return stable_suggestion
        return KEEP_IN_INBOX

    sender_text = _normalize(_extract_sender_text(message))
    subject = _normalize(message.get("subject"))
    body_preview = _normalize(message.get("bodyPreview"))
    sender_or_subject = f"{sender_text} {subject}"
    newsletter_text = f"{subject} {body_preview}"

    if any(term in sender_or_subject for term in ("amazon", "ebay", "paypal", "klarna")):
        return "Finanzen/Bestellungen"

    if any(
        term in subject
        for term in (
            "rechnung",
            "invoice",
            "beleg",
            "zahlungsbestätigung",
            "kontoauszug",
        )
    ):
        return "Finanzen/Rechnungen"

    if any(
        term in sender_or_subject
        for term in ("framer", "openai", "microsoft", "github")
    ):
        return "WorldofWorkflow/Tools"

    if any(term in subject for term in ("impressum", "datenschutz", "agb", "vertrag")):
        return "WorldofWorkflow/Rechtliches"

    if any(term in newsletter_text for term in ("unsubscribe", "abmelden")):
        return "Newsletter"

    return "Unsortiert prüfen"
