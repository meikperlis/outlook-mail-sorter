"""Small Microsoft Graph v1.0 client built on requests."""

from __future__ import annotations

from typing import Any

import requests

from config import GRAPH_BASE_URL


class GraphClient:
    """Minimal Graph client for the safe read-only stages."""

    def __init__(self, access_token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{GRAPH_BASE_URL}{path}"
        response = self.session.get(url, params=params, timeout=30)
        if not response.ok:
            raise RuntimeError(
                f"Graph-Anfrage fehlgeschlagen ({response.status_code}): {response.text}"
            )
        return response.json()

    def _post(self, path: str, json_body: dict[str, Any]) -> dict[str, Any]:
        url = f"{GRAPH_BASE_URL}{path}"
        response = self.session.post(url, json=json_body, timeout=30)
        if not response.ok:
            raise RuntimeError(
                f"Graph-Anfrage fehlgeschlagen ({response.status_code}): {response.text}"
            )
        return response.json()

    def get_me(self) -> dict[str, Any]:
        """Return profile information for the signed-in user."""
        return self._get("/me", params={"$select": "displayName,mail,userPrincipalName"})

    def list_top_level_mail_folders(self) -> list[dict[str, Any]]:
        """Return visible top-level mail folders below the mailbox root."""
        data = self._get(
            "/me/mailFolders",
            params={"$select": "id,displayName,totalItemCount,unreadItemCount"},
        )
        return data.get("value", [])

    def list_child_mail_folders(self, folder_id: str) -> list[dict[str, Any]]:
        """Return visible child folders for one parent folder."""
        data = self._get(
            f"/me/mailFolders/{folder_id}/childFolders",
            params={"$select": "id,displayName,totalItemCount,unreadItemCount"},
        )
        return data.get("value", [])

    def create_top_level_mail_folder(self, display_name: str) -> dict[str, Any]:
        """Create one visible top-level mail folder."""
        return self._post(
            "/me/mailFolders",
            {"displayName": display_name, "isHidden": False},
        )

    def create_child_mail_folder(self, parent_folder_id: str, display_name: str) -> dict[str, Any]:
        """Create one visible child mail folder."""
        return self._post(
            f"/me/mailFolders/{parent_folder_id}/childFolders",
            {"displayName": display_name, "isHidden": False},
        )

    def move_message(self, message_id: str, destination_folder_id: str) -> dict[str, Any]:
        """Move one message to another folder in the same mailbox."""
        return self._post(
            f"/me/messages/{message_id}/move",
            {"destinationId": destination_folder_id},
        )

    def list_inbox_messages(self, top: int = 10) -> list[dict[str, Any]]:
        """Return a small inbox sample for dry-run analysis."""
        data = self._get(
            "/me/mailFolders/inbox/messages",
            params={
                "$top": top,
                "$select": "id,sender,subject,receivedDateTime,bodyPreview",
                "$orderby": "receivedDateTime desc",
            },
        )
        return data.get("value", [])

    def list_recent_inbox_messages(self, top: int) -> list[dict[str, Any]]:
        """Return a larger inbox batch for controlled backfill runs."""
        data = self._get(
            "/me/mailFolders/inbox/messages",
            params={
                "$top": top,
                "$select": "id,sender,subject,receivedDateTime,bodyPreview",
                "$orderby": "receivedDateTime desc",
            },
        )
        return data.get("value", [])

    def list_recent_messages(self, top: int = 200) -> list[dict[str, Any]]:
        """Return a broader recent mailbox sample for structure analysis."""
        data = self._get(
            "/me/messages",
            params={
                "$top": top,
                "$select": "id,sender,subject,receivedDateTime,bodyPreview",
                "$orderby": "receivedDateTime desc",
            },
        )
        return data.get("value", [])
