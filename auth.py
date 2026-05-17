"""Authentication helpers using MSAL Python and Device Code Flow."""

from __future__ import annotations

from typing import Any

import msal

from config import AUTHORITY, CLIENT_ID, SCOPES, TOKEN_CACHE_FILE, validate_config
from state_store import LocalStateStore, StateStore


TOKEN_CACHE_NAME = "token_cache.json"


def _load_cache(store: StateStore) -> msal.SerializableTokenCache:
    """Load an MSAL cache if present."""
    cache = msal.SerializableTokenCache()
    raw = store.read_text(TOKEN_CACHE_NAME)
    if raw:
        cache.deserialize(raw)
    return cache


def _save_cache(cache: msal.SerializableTokenCache, store: StateStore) -> None:
    """Persist the MSAL cache only when it changed."""
    if cache.has_state_changed:
        store.write_text(TOKEN_CACHE_NAME, cache.serialize())


def _build_app(cache: msal.SerializableTokenCache) -> msal.PublicClientApplication:
    """Create the public client app used for delegated sign-in."""
    return msal.PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )


def get_access_token(
    state_store: StateStore | None = None,
    allow_interactive: bool = True,
) -> str:
    """
    Return an access token.

    Tries the local cache first and falls back to Device Code Flow only when needed.
    """
    validate_config()
    store = state_store or LocalStateStore(TOKEN_CACHE_FILE.parent)
    cache = _load_cache(store)
    app = _build_app(cache)

    accounts = app.get_accounts()
    result: dict[str, Any] | None = None

    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result and allow_interactive:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Device Code Flow konnte nicht gestartet werden: {flow}")

        print("\nAnmeldung erforderlich.")
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)

    _save_cache(cache, store)

    if not result or "access_token" not in result:
        if not allow_interactive:
            raise RuntimeError(
                "Kein gültiger Token-Cache verfügbar. "
                "Bitte lokal erneut anmelden und token_cache.json in den Cloud-Speicher hochladen."
            )
        error = result.get("error") if result else "unknown_error"
        description = result.get("error_description") if result else "Keine Details verfügbar."
        raise RuntimeError(f"Anmeldung fehlgeschlagen: {error} - {description}")

    return result["access_token"]
