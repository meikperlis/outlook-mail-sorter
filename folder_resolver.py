"""Resolve desired folder paths against the existing Outlook folder tree."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graph_client import GraphClient


@dataclass(frozen=True)
class FolderResolution:
    """Result of resolving one desired folder path."""

    path: str
    exists: bool
    existing_path: str
    missing_path: str
    resolved_folder_id: str | None


@dataclass(frozen=True)
class FolderCreationResult:
    """Result of ensuring a full path exists."""

    path: str
    created_paths: tuple[str, ...]
    final_folder_id: str


class FolderResolver:
    """Read-only resolver for hierarchical mail-folder paths."""

    def __init__(self, graph: "GraphClient", top_level_folders: list[dict]) -> None:
        self.graph = graph
        self._top_level_folders = top_level_folders
        self._children_cache: dict[str, list[dict]] = {}

    @staticmethod
    def _normalize(name: str | None) -> str:
        return (name or "").casefold()

    def _find_by_name(self, folders: list[dict], segment: str) -> dict | None:
        wanted = self._normalize(segment)
        return next(
            (
                folder
                for folder in folders
                if self._normalize(folder.get("displayName")) == wanted
            ),
            None,
        )

    def _children_of(self, parent_folder_id: str) -> list[dict]:
        if parent_folder_id not in self._children_cache:
            self._children_cache[parent_folder_id] = self.graph.list_child_mail_folders(
                parent_folder_id
            )
        return self._children_cache[parent_folder_id]

    def resolve(self, path: str) -> FolderResolution:
        """
        Resolve a slash-separated folder path without creating anything.

        Example:
            Finanzen/Rechnungen
        """
        segments = [segment.strip() for segment in path.split("/") if segment.strip()]
        if not segments:
            raise ValueError("Ordnerpfad darf nicht leer sein.")

        folders_at_level = self._top_level_folders
        existing_segments: list[str] = []
        current_folder_id: str | None = None

        for index, segment in enumerate(segments):
            matched = self._find_by_name(folders_at_level, segment)
            if not matched:
                missing_segments = segments[index:]
                return FolderResolution(
                    path=path,
                    exists=False,
                    existing_path="/".join(existing_segments),
                    missing_path="/".join(missing_segments),
                    resolved_folder_id=None,
                )

            existing_segments.append(matched.get("displayName") or segment)
            current_folder_id = matched.get("id")

            if index < len(segments) - 1:
                if not current_folder_id:
                    missing_segments = segments[index + 1 :]
                    return FolderResolution(
                        path=path,
                        exists=False,
                        existing_path="/".join(existing_segments),
                        missing_path="/".join(missing_segments),
                        resolved_folder_id=None,
                    )
                folders_at_level = self._children_of(current_folder_id)

        return FolderResolution(
            path=path,
            exists=True,
            existing_path="/".join(existing_segments),
            missing_path="",
            resolved_folder_id=current_folder_id,
        )

    def ensure_exists(self, path: str) -> FolderCreationResult:
        """
        Create only the missing segments of a path.

        This method is intentionally separate from ``resolve`` so callers can keep
        read-only and write-capable flows distinct.
        """
        segments = [segment.strip() for segment in path.split("/") if segment.strip()]
        if not segments:
            raise ValueError("Ordnerpfad darf nicht leer sein.")

        folders_at_level = self._top_level_folders
        created_paths: list[str] = []
        built_segments: list[str] = []
        current_folder_id: str | None = None

        for index, segment in enumerate(segments):
            matched = self._find_by_name(folders_at_level, segment)
            if matched:
                built_segments.append(matched.get("displayName") or segment)
                current_folder_id = matched.get("id")
            else:
                if index == 0:
                    created = self.graph.create_top_level_mail_folder(segment)
                    self._top_level_folders.append(created)
                else:
                    if not current_folder_id:
                        raise RuntimeError(
                            f"Elternordner für '{segment}' konnte nicht bestimmt werden."
                        )
                    created = self.graph.create_child_mail_folder(current_folder_id, segment)
                    self._children_cache.setdefault(current_folder_id, []).append(created)

                built_segments.append(created.get("displayName") or segment)
                current_folder_id = created.get("id")
                created_paths.append("/".join(built_segments))

            if not current_folder_id:
                raise RuntimeError(f"Ordner-ID für '{'/'.join(built_segments)}' fehlt.")

            if index < len(segments) - 1:
                folders_at_level = self._children_of(current_folder_id)

        return FolderCreationResult(
            path=path,
            created_paths=tuple(created_paths),
            final_folder_id=current_folder_id,
        )
