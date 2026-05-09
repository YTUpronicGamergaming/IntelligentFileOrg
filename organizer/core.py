"""
core.py
-------
The FileOrganizer is the top-level façade that:
  1. Accepts a source directory and optional overrides.
  2. Builds all sub-components (Scanner, Categorizer, FileMover).
  3. Runs them in the correct order.
  4. Reports a structured summary when finished.

Design decisions:
  - Façade pattern: callers (main.py, tests, future GUI) interact only with
    FileOrganizer and never import sub-modules directly.
  - Timing is measured at orchestrator level so wall-clock time includes I/O.
  - run() returns an OrganizeResult dataclass so callers can react
    programmatically (GUI results table, test assertions) rather than parsing
    log output.

v1.1 additions
--------------
  - FileOrganizer accepts `exclude_dash_folders` as a constructor override.
  - run() calls scanner.excluded_dirs after the file scan is complete, then
    delegates whole-directory moves to FileMover.move_folders().
  - OrganizeResult now carries folder_results and exposes folder-specific
    summary properties. print_summary() includes an Excluded Folders section
    when any were processed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .categorizer import Categorizer, CategoryPlugin
from .config_manager import OrganizerConfig, load_config
from .logger import get_logger, get_child_logger
from .mover import FileMover, FolderMoveResult, MoveResult, MoveStatus
from .scanner import DashFolderInfo, DirectoryScanner, FileInfo

log = get_child_logger("core")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class OrganizeResult:
    """Summary returned by FileOrganizer.run()."""

    source_dir: Path
    output_dir: Path
    preview_mode: bool
    elapsed_seconds: float
    results: List[MoveResult] = field(default_factory=list)
    folder_results: List[FolderMoveResult] = field(default_factory=list)

    # ── File counts ────────────────────────────────────────────────────

    @property
    def moved(self) -> int:
        return sum(1 for r in self.results if r.status == MoveStatus.MOVED)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == MoveStatus.SKIPPED)

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.status == MoveStatus.ERROR)

    @property
    def previewed(self) -> int:
        return sum(1 for r in self.results if r.status == MoveStatus.PREVIEW)

    @property
    def total(self) -> int:
        return len(self.results)

    # ── Folder counts ──────────────────────────────────────────────────

    @property
    def folders_moved(self) -> int:
        return sum(1 for r in self.folder_results if r.status == MoveStatus.MOVED)

    @property
    def folders_previewed(self) -> int:
        return sum(1 for r in self.folder_results if r.status == MoveStatus.PREVIEW)

    @property
    def folders_errored(self) -> int:
        return sum(1 for r in self.folder_results if r.status == MoveStatus.ERROR)

    @property
    def total_folders(self) -> int:
        return len(self.folder_results)

    # ── Summary printer ────────────────────────────────────────────────

    def print_summary(self) -> None:
        """Print a formatted summary table to stdout."""
        mode = "PREVIEW" if self.preview_mode else "LIVE"
        w = 54
        print("\n" + "=" * w)
        print(f"  Intelligent File Organizer — {mode} RUN")
        print("=" * w)
        print(f"  Source  : {self.source_dir}")
        print(f"  Output  : {self.output_dir}")
        print(f"  Time    : {self.elapsed_seconds:.2f}s")
        print("-" * w)

        # Files section
        print("  Files")
        if self.preview_mode:
            print(f"    Would move   : {self.previewed}")
        else:
            print(f"    Moved        : {self.moved}")
        print(f"    Skipped      : {self.skipped}")
        print(f"    Errors       : {self.errors}")
        print(f"    Total        : {self.total}")

        # Excluded folders section (only shown when relevant)
        if self.total_folders > 0:
            print("-" * w)
            print("  Excluded Dash-Folders")
            if self.preview_mode:
                print(f"    Would move   : {self.folders_previewed}")
            else:
                print(f"    Moved        : {self.folders_moved}")
            if self.folders_errored:
                print(f"    Errors       : {self.folders_errored}")
            print(f"    Total        : {self.total_folders}")

        print("=" * w + "\n")

        # Error detail
        all_errors = (
            [r for r in self.results if r.status == MoveStatus.ERROR]
            + [r for r in self.folder_results if r.status == MoveStatus.ERROR]
        )
        if all_errors:
            print("  Errors encountered:")
            for r in all_errors:
                name = (
                    r.file_info.name
                    if isinstance(r, MoveResult)
                    else r.folder_info.name + "/"
                )
                print(f"    • {name}: {r.error_message}")
            print()


# ---------------------------------------------------------------------------
# Main organizer class
# ---------------------------------------------------------------------------

class FileOrganizer:
    """
    High-level façade for the file organisation pipeline.

    Basic usage
    -----------
    organizer = FileOrganizer(
        source_dir="/Users/me/Downloads",
        output_dir="/Users/me/Organized",   # defaults to source_dir if omitted
        preview_mode=True,
    )
    result = organizer.run()
    result.print_summary()

    Dash-folder exclusion
    ---------------------
    By default, any top-level directory whose name starts with '-' is moved
    wholesale into output_dir/Excluded/ rather than having its contents
    scanned and categorized.

    To disable:
        FileOrganizer(..., exclude_dash_folders=False)

    Plugin API
    ----------
    organizer.register_plugin(MyAIPlugin())  # called for uncategorized files
    """

    def __init__(
        self,
        source_dir: str | Path,
        output_dir: Optional[str | Path] = None,
        config_path: Optional[str | Path] = None,
        preview_mode: Optional[bool] = None,
        recursive: Optional[bool] = None,
        exclude_dash_folders: Optional[bool] = None,   # v1.1
        log_to_file: Optional[bool] = None,
        log_file: Optional[str | Path] = None,
    ) -> None:
        # Resolve paths
        self._source = Path(source_dir).resolve()
        self._output = Path(output_dir).resolve() if output_dir else self._source

        # Load config (CLI/constructor overrides take precedence)
        self._config: OrganizerConfig = load_config(config_path)
        s = self._config.settings

        if preview_mode is not None:
            s.preview_mode = preview_mode
        if recursive is not None:
            s.recursive = recursive
        if exclude_dash_folders is not None:
            s.exclude_dash_folders = exclude_dash_folders

        # Set up root logger (idempotent — safe to call multiple times)
        _log_to_file = log_to_file if log_to_file is not None else s.log_to_file
        _log_file = log_file or s.log_filename
        get_logger(log_to_file=_log_to_file, log_file=_log_file)

        # Plugin registry for custom categorizers
        self._plugins: List[CategoryPlugin] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_plugin(self, plugin: CategoryPlugin) -> "FileOrganizer":
        """
        Register a custom CategoryPlugin (e.g. an AI classifier).
        Returns self for fluent chaining.
        """
        self._plugins.append(plugin)
        return self

    def run(self) -> OrganizeResult:
        """
        Execute the full organisation pipeline and return a summary.

        Pipeline steps
        --------------
        1. Scan source directory for files.
           Side effect: scanner captures dash-dirs into excluded_dirs.
        2. Categorize each file.
        3. Move files (or simulate in preview mode).
        4. Move excluded dash-dirs as-is (or simulate in preview mode).
        5. Return structured OrganizeResult.
        """
        s = self._config.settings

        log.info(
            f"Starting organizer | source={self._source} | output={self._output} | "
            f"preview={s.preview_mode} | recursive={s.recursive} | "
            f"exclude_dash={s.exclude_dash_folders}"
        )

        start = time.perf_counter()

        # ── Step 1: Scan ───────────────────────────────────────────────
        scanner = DirectoryScanner(
            target=self._source,
            recursive=s.recursive,
            skip_hidden=s.skip_hidden_files,
            skip_system=s.skip_system_files,
            system_patterns=s.system_file_patterns,
            min_size_bytes=s.min_file_size_bytes,
            max_size_mb=s.max_file_size_mb,
            exclude_dash_folders=s.exclude_dash_folders,
        )

        # Exhaust the generator so _excluded_dirs is fully populated
        files: List[FileInfo] = list(scanner.scan())
        excluded_dirs: List[DashFolderInfo] = scanner.excluded_dirs

        if not files and not excluded_dirs:
            log.info("No files or excluded folders found. Nothing to do.")
            elapsed = time.perf_counter() - start
            return OrganizeResult(
                source_dir=self._source,
                output_dir=self._output,
                preview_mode=s.preview_mode,
                elapsed_seconds=elapsed,
            )

        # ── Step 2: Categorize ─────────────────────────────────────────
        categorizer = Categorizer(self._config)
        for plugin in self._plugins:
            categorizer.register_plugin(plugin)

        categorized = categorizer.categorize_many(files)

        # ── Steps 3 + 4: Move files and excluded folders ──────────────
        mover = FileMover(
            output_root=self._output,
            preview_mode=s.preview_mode,
            duplicate_strategy=s.duplicate_strategy,
        )

        move_results = mover.move_many(categorized)

        folder_results: List[FolderMoveResult] = []
        if excluded_dirs:
            excluded_root = self._output / s.excluded_folder
            log.info(
                f"Moving {len(excluded_dirs)} excluded dash-folder(s) "
                f"→ {s.excluded_folder}/"
            )
            folder_results = mover.move_folders(excluded_dirs, excluded_root)

        elapsed = time.perf_counter() - start
        log.info(f"Finished in {elapsed:.2f}s")

        return OrganizeResult(
            source_dir=self._source,
            output_dir=self._output,
            preview_mode=s.preview_mode,
            elapsed_seconds=elapsed,
            results=move_results,
            folder_results=folder_results,
        )