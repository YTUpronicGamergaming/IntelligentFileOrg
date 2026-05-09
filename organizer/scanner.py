"""
scanner.py
----------
Responsible for discovering files within a target directory.

Design decisions:
  - Uses pathlib.Path throughout for cross-platform compatibility.
  - Yields FileInfo objects (lightweight dataclasses) rather than raw Paths,
    so downstream components always have pre-computed metadata.
  - Filtering (hidden, system, size limits) is applied here to keep the
    categorizer and mover focused on their single responsibilities.
  - Generator-based scan(): memory usage stays constant for millions of files.

v1.1 additions — Dash-folder exclusion
---------------------------------------
Directories whose names start with '-' (e.g. -Personal, -Archive) are treated
as "excluded" rather than scanned:

  Behaviour when exclude_dash_folders=True (default):
  - In NON-RECURSIVE mode:
      Top-level dash-dirs in the source are captured as DashFolderInfo objects.
      Their contents are never visited or yielded.
  - In RECURSIVE mode:
      Dash-dirs at ANY depth are removed from os.walk's directory list,
      preventing descent. They are captured as DashFolderInfo.
      Note: in recursive mode only dash-dirs at the IMMEDIATE children of a
      scanned directory are intercepted (first time os.walk sees them).

  Access excluded dirs AFTER exhausting scan():
      scanner = DirectoryScanner(...)
      files = list(scanner.scan())      # populates _excluded_dirs
      excluded = scanner.excluded_dirs  # now safe to read

  Behaviour when exclude_dash_folders=False:
      Dash-dirs are treated as ordinary directories; no DashFolderInfo is
      created. scan() descends into them (if recursive) or ignores them
      (if non-recursive, as before).
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, List, Optional

from .logger import get_child_logger

log = get_child_logger("scanner")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FileInfo:
    """
    Lightweight snapshot of a discovered file.

    Attributes
    ----------
    path            : Absolute path to the file.
    extension       : Lowercase extension without the leading dot (e.g. 'pdf').
    size_bytes      : File size in bytes at scan time.
    name            : Filename including extension.
    stem            : Filename without extension.
    relative_path   : Path relative to the scanned root.
    category        : Set by Categorizer (e.g. 'Documents').
    subcategory     : Set by Categorizer (e.g. 'PDF').
    destination     : Set by FileMover before the actual move.
    """

    path: Path
    extension: str
    size_bytes: int
    name: str
    stem: str
    relative_path: Path

    category: str = ""
    subcategory: str = ""
    destination: Optional[Path] = None

    @classmethod
    def from_path(cls, file_path: Path, root: Path) -> "FileInfo":
        stat = file_path.stat()
        ext = file_path.suffix.lstrip(".").lower()
        return cls(
            path=file_path.resolve(),
            extension=ext,
            size_bytes=stat.st_size,
            name=file_path.name,
            stem=file_path.stem,
            relative_path=file_path.relative_to(root),
        )

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


@dataclass
class DashFolderInfo:
    """
    Represents a directory whose name starts with '-'.

    These directories are excluded from content scanning. Their entire
    tree is moved as-is to the 'Excluded' destination folder.

    Attributes
    ----------
    path            : Absolute path to the directory.
    name            : Directory name (e.g. '-Personal').
    relative_path   : Path relative to the scanned root.
    destination     : Set by FileMover before the actual move.
    """

    path: Path
    name: str
    relative_path: Path
    destination: Optional[Path] = None

    @classmethod
    def from_path(cls, dir_path: Path, root: Path) -> "DashFolderInfo":
        return cls(
            path=dir_path.resolve(),
            name=dir_path.name,
            relative_path=dir_path.relative_to(root),
        )


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class DirectoryScanner:
    """
    Walks a target directory and yields FileInfo objects for every qualifying
    file. Optionally captures dash-prefixed directories as DashFolderInfo
    rather than descending into them.

    Usage (files only)
    ------------------
    scanner = DirectoryScanner(target=Path("/downloads"), recursive=True)
    for file_info in scanner.scan():
        print(file_info.name)

    Usage (files + excluded dash-folders)
    --------------------------------------
    scanner = DirectoryScanner(
        target=Path("/downloads"),
        recursive=True,
        exclude_dash_folders=True,   # default
    )
    files = list(scanner.scan())       # MUST exhaust generator first
    excluded = scanner.excluded_dirs   # then access excluded dirs
    """

    def __init__(
        self,
        target: Path,
        recursive: bool = False,
        skip_hidden: bool = True,
        skip_system: bool = True,
        system_patterns: Optional[List[str]] = None,
        min_size_bytes: int = 0,
        max_size_mb: Optional[float] = None,
        exclude_dash_folders: bool = True,
    ) -> None:
        self._target = target
        self._recursive = recursive
        self._skip_hidden = skip_hidden
        self._skip_system = skip_system
        self._system_patterns: List[str] = system_patterns or []
        self._min_size = min_size_bytes
        self._max_size = max_size_mb
        self._exclude_dash_folders = exclude_dash_folders

        # Populated during scan(); read via .excluded_dirs property afterward.
        self._excluded_dirs: List[DashFolderInfo] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self) -> Generator[FileInfo, None, None]:
        """
        Yield FileInfo for each qualifying file in the target directory.

        Side effect: populates self._excluded_dirs with any dash-prefixed
        directories encountered. Access self.excluded_dirs after the generator
        is fully consumed.

        Raises
        ------
        FileNotFoundError  : Target directory does not exist.
        NotADirectoryError : Target path is a file, not a directory.
        PermissionError    : Insufficient access to the target directory.
        """
        # Reset excluded dirs at the start of each scan call so the scanner
        # is safe to reuse (e.g. in tests).
        self._excluded_dirs = []
        self._validate_target()

        log.info(
            f"Scanning: {self._target}  "
            f"(recursive={self._recursive}, "
            f"exclude_dash={self._exclude_dash_folders})"
        )
        count = 0

        for entry in self._walk():
            try:
                info = FileInfo.from_path(entry, self._target)
            except (OSError, PermissionError) as exc:
                log.warning(f"Could not stat file, skipping: {entry}  ({exc})")
                continue

            if not self._passes_filters(info):
                continue

            count += 1
            yield info

        excluded_count = len(self._excluded_dirs)
        log.info(
            f"Scan complete. {count} file(s) found"
            + (f", {excluded_count} dash-folder(s) excluded." if excluded_count else ".")
        )

    def count(self) -> int:
        """Return the total number of qualifying files without yielding them."""
        return sum(1 for _ in self.scan())

    @property
    def excluded_dirs(self) -> List[DashFolderInfo]:
        """
        Dash-prefixed directories captured during the most recent scan().

        Only valid after the scan() generator has been fully consumed.
        Returns a copy to prevent external mutation.
        """
        return list(self._excluded_dirs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_target(self) -> None:
        if not self._target.exists():
            raise FileNotFoundError(f"Target directory not found: {self._target}")
        if not self._target.is_dir():
            raise NotADirectoryError(f"Target is not a directory: {self._target}")

    def _walk(self) -> Generator[Path, None, None]:
        """
        Yield file paths respecting recursive mode and dash-folder exclusion.

        Non-recursive mode:
            Iterates the top-level entries only. Dash-dirs and other directories
            are not yielded as files; dash-dirs are captured as DashFolderInfo.

        Recursive mode:
            Uses os.walk with in-place dir list modification to prune:
              - Hidden directories (if skip_hidden=True)
              - Dash-prefixed directories (if exclude_dash_folders=True)
            Pruned dash-dirs are added to self._excluded_dirs.
        """
        if self._recursive:
            yield from self._walk_recursive()
        else:
            yield from self._walk_flat()

    def _walk_recursive(self) -> Generator[Path, None, None]:
        for root, dirs, files in os.walk(self._target):
            root_path = Path(root)

            # ── Prune hidden directories (modifies dirs in-place) ──────────
            if self._skip_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]

            # ── Prune and capture dash-prefixed directories ────────────────
            if self._exclude_dash_folders:
                dash, normal = [], []
                for d in dirs:
                    if d.startswith("-"):
                        dash.append(d)
                    else:
                        normal.append(d)
                dirs[:] = normal  # Prevent os.walk from descending into dash dirs

                for d in dash:
                    dir_path = root_path / d
                    info = DashFolderInfo.from_path(dir_path, self._target)
                    self._excluded_dirs.append(info)
                    log.debug(f"Excluded dash-folder: {info.relative_path}/")

            # ── Yield files in this directory ──────────────────────────────
            for filename in files:
                yield root_path / filename

    def _walk_flat(self) -> Generator[Path, None, None]:
        """Iterate only the immediate children of the target directory."""
        for entry in self._target.iterdir():
            if entry.is_dir():
                if self._exclude_dash_folders and entry.name.startswith("-"):
                    info = DashFolderInfo.from_path(entry, self._target)
                    self._excluded_dirs.append(info)
                    log.debug(f"Excluded dash-folder: {info.name}/")
                # Other directories are silently skipped in flat mode
            elif entry.is_file():
                yield entry

    def _passes_filters(self, info: FileInfo) -> bool:
        """Return True if the file should be included in the scan results."""

        # Hidden file check
        if self._skip_hidden and info.name.startswith("."):
            log.debug(f"Skipping hidden file: {info.name}")
            return False

        # System file pattern check (e.g. Thumbs.db, desktop.ini)
        if self._skip_system:
            for pattern in self._system_patterns:
                if fnmatch.fnmatch(info.name, pattern):
                    log.debug(f"Skipping system file: {info.name}")
                    return False

        # Size checks
        if info.size_bytes < self._min_size:
            log.debug(f"Skipping too-small file ({info.size_bytes}B): {info.name}")
            return False

        if self._max_size is not None and info.size_mb > self._max_size:
            log.debug(f"Skipping too-large file ({info.size_mb:.1f}MB): {info.name}")
            return False

        return True