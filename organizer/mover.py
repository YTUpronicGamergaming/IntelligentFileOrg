"""
mover.py
--------
Handles the actual file-system I/O: creating destination directories and
moving files (and whole excluded directories) safely.

Key behaviours
--------------
- Preview mode: logs what *would* happen without touching the filesystem.
- Automatic parent directory creation (makedirs with exist_ok=True).
- Per-operation error isolation: one locked file never aborts the whole run.
- Move history: records every result for summary reporting and future undo.
- Cross-device moves: shutil.move handles moves across drive letters/mounts.

v1.1 additions
--------------
FolderMoveResult
    Parallel to MoveResult but holds a DashFolderInfo instead of a FileInfo.
    Returned by move_folder() and move_folders().

FileMover.move_folder(folder_info, excluded_root)
    Moves an entire dash-prefixed directory as-is to the excluded_root.
    Applies the same duplicate counter logic as individual files.

FileMover.move_folders(folder_infos, excluded_root)
    Batch wrapper around move_folder().
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional

from .duplicate_handler import Strategy, resolve
from .logger import get_child_logger
from .scanner import DashFolderInfo, FileInfo

log = get_child_logger("mover")


# ---------------------------------------------------------------------------
# Shared status enum
# ---------------------------------------------------------------------------

class MoveStatus(Enum):
    MOVED    = auto()
    SKIPPED  = auto()   # duplicate_strategy=skip and destination already exists
    ERROR    = auto()
    PREVIEW  = auto()   # preview mode — no actual I/O performed


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MoveResult:
    """Record of a single file move operation."""

    file_info: FileInfo
    status: MoveStatus
    source: Path
    destination: Optional[Path]
    error_message: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (MoveStatus.MOVED, MoveStatus.PREVIEW)


@dataclass
class FolderMoveResult:
    """
    Record of a single excluded-directory move operation.

    Mirrors MoveResult but stores a DashFolderInfo instead of a FileInfo,
    keeping the type system clean without any awkward Optional fields.
    """

    folder_info: DashFolderInfo
    status: MoveStatus
    source: Path
    destination: Optional[Path]
    error_message: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (MoveStatus.MOVED, MoveStatus.PREVIEW)


# ---------------------------------------------------------------------------
# FileMover
# ---------------------------------------------------------------------------

class FileMover:
    """
    Moves files and excluded directories to their computed destinations.

    Parameters
    ----------
    output_root        : Root directory where organised folders are created.
    preview_mode       : If True, log planned operations without any I/O.
    duplicate_strategy : How to handle filename/dirname conflicts.
    """

    def __init__(
        self,
        output_root: Path,
        preview_mode: bool = False,
        duplicate_strategy: Strategy = "counter",
    ) -> None:
        self._root = output_root
        self._preview = preview_mode
        self._dup_strategy = duplicate_strategy
        self._history: List[MoveResult] = []
        self._folder_history: List[FolderMoveResult] = []

    # ------------------------------------------------------------------
    # File operations (unchanged public API)
    # ------------------------------------------------------------------

    def move(self, file_info: FileInfo) -> MoveResult:
        """
        Move a single file to its category destination.

        Destination is computed from file_info.category and .subcategory.
        Duplicate resolution is applied automatically.
        """
        destination = self._compute_file_destination(file_info)
        resolved = resolve(destination, self._dup_strategy)

        if resolved is None:
            result = MoveResult(
                file_info=file_info,
                status=MoveStatus.SKIPPED,
                source=file_info.path,
                destination=destination,
            )
            log.warning(f"[SKIP]     {file_info.name}  (already exists at destination)")

        elif self._preview:
            result = MoveResult(
                file_info=file_info,
                status=MoveStatus.PREVIEW,
                source=file_info.path,
                destination=resolved,
            )
            log.info(f"[PREVIEW]  {file_info.name}  →  {self._rel(resolved)}")

        else:
            result = self._do_file_move(file_info, resolved)

        self._history.append(result)
        return result

    def move_many(self, files: List[FileInfo]) -> List[MoveResult]:
        """Move a batch of files; return one result per file."""
        return [self.move(f) for f in files]

    # ------------------------------------------------------------------
    # Folder operations (v1.1)
    # ------------------------------------------------------------------

    def move_folder(
        self,
        folder_info: DashFolderInfo,
        excluded_root: Path,
    ) -> FolderMoveResult:
        """
        Move an entire dash-prefixed directory into the excluded_root folder.

        The folder's name is preserved. If a directory with the same name
        already exists at the destination, a counter suffix is appended:
            -Personal → -Personal (1) → -Personal (2)

        Parameters
        ----------
        folder_info   : DashFolderInfo captured by the scanner.
        excluded_root : Top-level folder for excluded dirs (e.g. output/Excluded).
        """
        destination = excluded_root / folder_info.name

        # Resolve destination conflict for directories
        resolved = self._resolve_dir_conflict(destination)

        if self._preview:
            result = FolderMoveResult(
                folder_info=folder_info,
                status=MoveStatus.PREVIEW,
                source=folder_info.path,
                destination=resolved,
            )
            log.info(
                f"[PREVIEW]  📁 {folder_info.name}/  →  "
                f"{excluded_root.name}/{resolved.name}/"
            )

        else:
            result = self._do_folder_move(folder_info, resolved, excluded_root)

        self._folder_history.append(result)
        return result

    def move_folders(
        self,
        folders: List[DashFolderInfo],
        excluded_root: Path,
    ) -> List[FolderMoveResult]:
        """Move a batch of excluded directories; return one result per folder."""
        return [self.move_folder(f, excluded_root) for f in folders]

    # ------------------------------------------------------------------
    # History / stats
    # ------------------------------------------------------------------

    @property
    def history(self) -> List[MoveResult]:
        """All file move results accumulated during this session."""
        return list(self._history)

    @property
    def folder_history(self) -> List[FolderMoveResult]:
        """All folder move results accumulated during this session."""
        return list(self._folder_history)

    @property
    def stats(self) -> dict:
        """Summary counts broken down by status (files only)."""
        from collections import Counter
        counts = Counter(r.status for r in self._history)
        return {
            "moved":   counts[MoveStatus.MOVED],
            "skipped": counts[MoveStatus.SKIPPED],
            "errors":  counts[MoveStatus.ERROR],
            "preview": counts[MoveStatus.PREVIEW],
            "total":   len(self._history),
        }

    # ------------------------------------------------------------------
    # Internal helpers — files
    # ------------------------------------------------------------------

    def _compute_file_destination(self, file_info: FileInfo) -> Path:
        """Build the full destination path for a categorized file."""
        parts = [file_info.category]
        if file_info.subcategory:
            parts.append(file_info.subcategory)
        return self._root.joinpath(*parts, file_info.name)

    def _do_file_move(self, file_info: FileInfo, destination: Path) -> MoveResult:
        """Perform the actual file move with full error isolation."""
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file_info.path), str(destination))

            renamed = destination.name != file_info.name
            suffix = f"  (renamed: {destination.name})" if renamed else ""
            log.info(f"[MOVED]    {file_info.name}  →  {self._rel(destination)}{suffix}")

            return MoveResult(
                file_info=file_info,
                status=MoveStatus.MOVED,
                source=file_info.path,
                destination=destination,
            )

        except PermissionError as exc:
            return self._file_error(file_info, destination, f"Permission denied: {exc}")
        except FileNotFoundError as exc:
            return self._file_error(file_info, destination, f"File disappeared: {exc}")
        except Exception as exc:
            return self._file_error(
                file_info, destination, f"{type(exc).__name__}: {exc}"
            )

    def _file_error(
        self, file_info: FileInfo, destination: Path, msg: str
    ) -> MoveResult:
        log.error(f"[ERROR]    {file_info.name}  —  {msg}")
        return MoveResult(
            file_info=file_info,
            status=MoveStatus.ERROR,
            source=file_info.path,
            destination=destination,
            error_message=msg,
        )

    # ------------------------------------------------------------------
    # Internal helpers — folders
    # ------------------------------------------------------------------

    def _resolve_dir_conflict(self, destination: Path) -> Path:
        """
        Return a path that does not currently exist, applying a counter suffix
        if needed.  Uses a simple integer loop capped at 9999.
        """
        if not destination.exists():
            return destination

        parent = destination.parent
        name   = destination.name

        for i in range(1, 10000):
            candidate = parent / f"{name} ({i})"
            if not candidate.exists():
                log.debug(
                    f"Dir conflict resolved: {name}/ → {candidate.name}/"
                )
                return candidate

        raise RuntimeError(
            f"Could not resolve directory conflict after 9999 attempts: {destination}"
        )

    def _do_folder_move(
        self,
        folder_info: DashFolderInfo,
        destination: Path,
        excluded_root: Path,
    ) -> FolderMoveResult:
        """Perform the actual whole-directory move with full error isolation."""
        try:
            excluded_root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(folder_info.path), str(destination))

            renamed = destination.name != folder_info.name
            suffix = f"  (renamed: {destination.name}/)" if renamed else ""
            log.info(
                f"[EXCLUDED] 📁 {folder_info.name}/  →  "
                f"{excluded_root.name}/{destination.name}/{suffix}"
            )

            return FolderMoveResult(
                folder_info=folder_info,
                status=MoveStatus.MOVED,
                source=folder_info.path,
                destination=destination,
            )

        except PermissionError as exc:
            return self._folder_error(
                folder_info, destination, f"Permission denied: {exc}"
            )
        except FileNotFoundError as exc:
            return self._folder_error(
                folder_info, destination, f"Folder disappeared: {exc}"
            )
        except Exception as exc:
            return self._folder_error(
                folder_info, destination, f"{type(exc).__name__}: {exc}"
            )

    def _folder_error(
        self, folder_info: DashFolderInfo, destination: Path, msg: str
    ) -> FolderMoveResult:
        log.error(f"[ERROR]    📁 {folder_info.name}/  —  {msg}")
        return FolderMoveResult(
            folder_info=folder_info,
            status=MoveStatus.ERROR,
            source=folder_info.path,
            destination=destination,
            error_message=msg,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _rel(self, path: Path) -> str:
        """Return path relative to the output root for concise log output."""
        try:
            return str(path.relative_to(self._root))
        except ValueError:
            return str(path)