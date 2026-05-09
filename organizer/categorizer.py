"""
categorizer.py
--------------
Maps a FileInfo object to a (category, subcategory) pair using:
  1. Extension-based lookup  (fast, primary method)
  2. MIME-type fallback       (covers exotic extensions like .pages)
  3. Uncategorized catch-all  (nothing matches → safe fallback)

Design decisions:
  - Separated from the Scanner so the categorization strategy can be swapped
    out independently (e.g. swap extension lookup for an AI classifier later).
  - The MIME fallback uses Python's built-in `mimetypes` module — zero extra
    dependencies, cross-platform, and handles a surprisingly wide range.
  - Hook-based architecture: register custom CategoryPlugin classes to extend
    classification without modifying core logic (Open/Closed principle).

Future AI hook
--------------
To add AI classification, implement the CategoryPlugin protocol and register
it via Categorizer.register_plugin(). The plugin is called only when the
standard lookup returns "Uncategorized", preventing unnecessary API calls.
"""

from __future__ import annotations

import mimetypes
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from .config_manager import OrganizerConfig
from .logger import get_child_logger
from .scanner import FileInfo

log = get_child_logger("categorizer")


# ---------------------------------------------------------------------------
# Plugin protocol (for future AI / custom categorizers)
# ---------------------------------------------------------------------------

class CategoryPlugin(ABC):
    """
    Interface for pluggable categorization strategies.

    Implement this to add AI classification, content analysis, OCR, etc.
    Return None to signal "I don't know" and let the next plugin try.
    """

    @abstractmethod
    def categorize(self, file_info: FileInfo) -> Optional[Tuple[str, str]]:
        """
        Return (category, subcategory) or None if this plugin cannot classify
        the given file.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name used in log messages."""
        ...


# ---------------------------------------------------------------------------
# MIME-type fallback plugin (built-in)
# ---------------------------------------------------------------------------

# Coarse MIME prefix → category name mapping
_MIME_CATEGORY_MAP = {
    "image":       "Photos",
    "video":       "Videos",
    "audio":       "Audio",
    "text":        "Documents",
    "application": None,   # too broad — handle case-by-case below
}

_MIME_APPLICATION_MAP = {
    "pdf":       ("Documents", "PDF"),
    "zip":       ("Archives",  "ZIP"),
    "gzip":      ("Archives",  "GZ"),
    "x-rar":     ("Archives",  "RAR"),
    "x-7z":      ("Archives",  "7Z"),
    "msword":    ("Documents", "DOCX"),
    "vnd.ms-excel":   ("Documents", "XLSX"),
    "vnd.ms-powerpoint": ("Documents", "PPTX"),
    "vnd.openxmlformats-officedocument.wordprocessingml.document":    ("Documents", "DOCX"),
    "vnd.openxmlformats-officedocument.spreadsheetml.sheet":         ("Documents", "XLSX"),
    "vnd.openxmlformats-officedocument.presentationml.presentation":  ("Documents", "PPTX"),
    "x-python":  ("Code", "PY"),
    "javascript": ("Code", "JS"),
    "json":      ("Code", "JSON"),
    "xml":       ("Code", "XML"),
    "x-sh":      ("Code", "Shell"),
    "x-msdos-program": ("Executables", "Windows"),
    "x-msdownload":    ("Executables", "Windows"),
}


class MimePlugin(CategoryPlugin):
    """Falls back to Python's mimetypes database when extension lookup fails."""

    name = "mime_fallback"

    def categorize(self, file_info: FileInfo) -> Optional[Tuple[str, str]]:
        mime, _ = mimetypes.guess_type(file_info.name)
        if not mime:
            return None

        main, sub = mime.split("/", 1)

        # Direct prefix matches (image/*, video/*, audio/*)
        category = _MIME_CATEGORY_MAP.get(main)
        if category:
            log.debug(f"MIME match '{mime}' → {category}/Other  [{file_info.name}]")
            return (category, "Other")

        # Application/* — needs finer-grained handling
        if main == "application":
            for key, result in _MIME_APPLICATION_MAP.items():
                if key in sub:
                    log.debug(f"MIME match '{mime}' → {result}  [{file_info.name}]")
                    return result

        return None


# ---------------------------------------------------------------------------
# Main Categorizer
# ---------------------------------------------------------------------------

class Categorizer:
    """
    Classifies FileInfo objects and populates their category/subcategory fields.

    Pipeline
    --------
    1. Extension lookup in config (O(1) dict access).
    2. Plugin chain (MIME built-in, then any custom plugins).
    3. Uncategorized fallback.
    """

    def __init__(self, config: OrganizerConfig) -> None:
        self._config = config
        self._plugins: List[CategoryPlugin] = [MimePlugin()]

    def register_plugin(self, plugin: CategoryPlugin) -> None:
        """
        Add a custom categorization plugin to the end of the pipeline.

        Plugins are tried in registration order after the MIME fallback.
        The first plugin to return a non-None result wins.
        """
        self._plugins.append(plugin)
        log.debug(f"Registered plugin: {plugin.name}")

    def categorize(self, file_info: FileInfo) -> FileInfo:
        """
        Classify a FileInfo in-place and return it for chaining.

        Sets file_info.category and file_info.subcategory.
        """
        category, subcategory = self._classify(file_info)
        file_info.category = category
        file_info.subcategory = subcategory
        log.debug(f"Categorized: {file_info.name} → {category}/{subcategory}")
        return file_info

    def categorize_many(self, files: List[FileInfo]) -> List[FileInfo]:
        """Classify a batch of files, returning the same list (mutated in-place)."""
        return [self.categorize(f) for f in files]

    # ------------------------------------------------------------------
    # Internal classification logic
    # ------------------------------------------------------------------

    def _classify(self, file_info: FileInfo) -> Tuple[str, str]:
        # 1. Fast extension lookup
        if file_info.extension:
            result = self._config.resolve(file_info.extension)
            if result[0] != self._config.settings.uncategorized_folder:
                return result

        # 2. Plugin chain (MIME fallback + custom plugins)
        for plugin in self._plugins:
            try:
                result = plugin.categorize(file_info)
                if result is not None:
                    return result
            except Exception as exc:
                log.warning(f"Plugin '{plugin.name}' raised an error: {exc}")

        # 3. Uncategorized catch-all
        return (self._config.settings.uncategorized_folder, "")
