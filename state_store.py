"""State storage backends for local and Azure-hosted runs."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from azure.storage.blob import BlobServiceClient


class StateStore(Protocol):
    def read_text(self, name: str) -> str | None: ...

    def write_text(self, name: str, content: str) -> None: ...


class LocalStateStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def read_text(self, name: str) -> str | None:
        path = self.base_dir / name
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write_text(self, name: str, content: str) -> None:
        path = self.base_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class BlobStateStore:
    def __init__(self, connection_string: str, container_name: str) -> None:
        service = BlobServiceClient.from_connection_string(connection_string)
        self.container = service.get_container_client(container_name)

    def read_text(self, name: str) -> str | None:
        blob = self.container.get_blob_client(name)
        if not blob.exists():
            return None
        return blob.download_blob().readall().decode("utf-8")

    def write_text(self, name: str, content: str) -> None:
        self.container.get_blob_client(name).upload_blob(
            content.encode("utf-8"),
            overwrite=True,
        )
