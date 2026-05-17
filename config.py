"""Central configuration for the Outlook sorter."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

# Trage deine Application (client) ID hier direkt ein
# oder setze alternativ die Umgebungsvariable OUTLOOK_SORTER_CLIENT_ID.
CLIENT_ID = os.getenv("OUTLOOK_SORTER_CLIENT_ID", "HIER_DEINE_CLIENT_ID_EINTRAGEN")

# Für reine private Microsoft-Konten.
AUTHORITY = os.getenv("OUTLOOK_SORTER_AUTHORITY", "https://login.microsoftonline.com/consumers")

# Delegierte Microsoft-Graph-Scopes für MSAL.
# `offline_access` ist in der App-Registrierung erlaubt, wird bei MSAL aber
# nicht explizit angefordert, weil es zu den reservierten OIDC-Scopes gehört.
SCOPES = ["User.Read", "Mail.ReadWrite"]

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_CACHE_FILE = BASE_DIR / ".token_cache.json"
LOG_DIR = BASE_DIR / "logs"
TOPIC_MEMORY_FILE = BASE_DIR / "topic_memory.json"

# Standardmodus beim einfachen Aufruf `python main.py`.
DEFAULT_MODE = "preview"

# Zusätzliche gezielte Sicherheits-Schalter für den Apply-Modus.
# Selbst bei `python main.py apply` bleiben beide standardmäßig aus.
CREATE_MISSING_FOLDERS = os.getenv("CREATE_MISSING_FOLDERS", "false").casefold() == "true"
MOVE_MESSAGES = os.getenv("MOVE_MESSAGES", "false").casefold() == "true"

# Für den täglichen Lauf lesen wir bewusst nur eine kleine Inbox-Stichprobe.
MESSAGE_LIMIT = 10
BACKFILL_MESSAGE_LIMIT = 200

# Für die Struktur-Analyse nehmen wir mehr Historie, aber bleiben absichtlich
# in einer kompakten Stichprobe statt das ganze Postfach zu kartieren.
ANALYSIS_MESSAGE_LIMIT = 200

# Ein Thema soll erst dann als neue stabile Ordneridee gelten, wenn es mehrfach
# im echten Bestand vorkommt. So verhindern wir Ordnerexplosion durch Ausreißer.
MIN_MESSAGES_PER_TOPIC = 5

# Ein Thema gilt erst dann als langfristig stabil, wenn es in mehreren Läufen
# wiederkehrt und insgesamt genug Evidenz gesammelt hat.
MIN_RUNS_FOR_STABLE_TOPIC = 2
MIN_TOTAL_MESSAGES_FOR_STABLE_TOPIC = 10
MAX_RUNS_SINCE_LAST_SEEN_FOR_STABLE_TOPIC = 3
MIN_UNIQUE_SENDERS_FOR_STABLE_TOPIC = 2
STRONG_TOPIC_MESSAGE_THRESHOLD = 20
STRONG_TOPIC_UNIQUE_SENDERS_THRESHOLD = 5

# Selbst ein langfristig stabiles Thema soll keinen neuen Ordner erzeugen,
# wenn im aktuellen Lauf nur ein einzelner Ausreißer dorthin möchte.
MIN_TARGET_MESSAGES_TO_CREATE_FOLDER = 2


def validate_config() -> None:
    """Fail early when required configuration is missing."""
    if not CLIENT_ID or CLIENT_ID == "HIER_DEINE_CLIENT_ID_EINTRAGEN":
        raise ValueError(
            "CLIENT_ID fehlt. Trage sie in config.py ein oder setze "
            "OUTLOOK_SORTER_CLIENT_ID als Umgebungsvariable."
        )
