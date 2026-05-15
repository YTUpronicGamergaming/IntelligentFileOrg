"""
config_manager.py
-----------------
Responsible for loading, validating, and merging configuration files.

Design decisions:
- Supports both JSON and YAML out of the box.
- Deep-merges user config over defaults so users only need to specify overrides.
- Returns an immutable-style dataclass so the rest of the app can rely on
  typed, predictable settings rather than raw dict keys.

v1.1 additions
--------------
- exclude_dash_folders : bool  — whether to treat folders starting with '-' as
  excluded (move them whole instead of scanning their contents).
- excluded_folder : str  — name of the top-level destination folder for excluded
  directories (default: "Excluded").

v1.1.0 additions
----------------
- AppMetadata dataclass — carries app name, version, and GitHub release URLs.
  Parsed from the top-level "app" block in config.json and exposed on
  OrganizerConfig so the version_controller can read it without re-parsing
  the file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# App metadata dataclass  (v1.1.0)
# ---------------------------------------------------------------------------

@dataclass
class AppMetadata:
    """
    Typed representation of the top-level 'app' block in config.json.

    This is the single source of truth for version and GitHub release info.
    The version_controller module reads these values rather than hard-coding
    anything.
    """

    name: str = "Intelligent File Organizer"
    version: str = "1.1.0"
    github_repo: str = "YTUpronicGamergaming/IntelligentFileOrg"
    github_releases_url: str = (
        "https://github.com/YTUpronicGamergaming/IntelligentFileOrg/releases"
    )
    github_api_latest: str = (
        "https://api.github.com/repos/"
        "YTUpronicGamergaming/IntelligentFileOrg/releases/latest"
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppMetadata":
        """Build from a raw dict, ignoring unknown keys."""
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    @property
    def version_tag(self) -> str:
        """Return the version with a leading 'v' prefix (e.g. 'v1.1.0')."""
        v = self.version
        return v if v.startswith("v") else f"v{v}"


# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------

@dataclass
class OrganizerSettings:
    """Typed representation of the 'settings' block in config.json."""

    # ── Core behaviour ─────────────────────────────────────────────────────
    duplicate_strategy: str = "counter"     # counter | timestamp | skip
    recursive: bool = False
    preview_mode: bool = False

    # ── Logging ────────────────────────────────────────────────────────────
    log_to_file: bool = True
    log_filename: str = "organizer.log"

    # ── File filtering ─────────────────────────────────────────────────────
    skip_hidden_files: bool = True
    skip_system_files: bool = True
    system_file_patterns: List[str] = field(default_factory=list)
    min_file_size_bytes: int = 0
    max_file_size_mb: Optional[float] = None

    # ── Folder destinations ────────────────────────────────────────────────
    uncategorized_folder: str = "Uncategorized"

    # ── Dash-folder exclusion (v1.1) ───────────────────────────────────────
    exclude_dash_folders: bool = True
    """
    When True (default), any top-level directory whose name starts with '-'
    is treated as an excluded folder:
      - Its contents are never scanned or categorized.
      - The entire directory is moved as-is into `excluded_folder`.

    Example:
        Source:  -Personal/  (contains private.docx, notes.txt)
        Output:  Excluded/-Personal/  (folder moved intact, untouched)

    Set to False to disable this behaviour and scan dash-folders normally.
    """

    excluded_folder: str = "Excluded"
    """
    Name of the output folder that receives excluded (dash-prefixed) directories.
    This folder is created at the top level of the output directory alongside
    Documents/, Photos/, etc.
    """

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrganizerSettings":
        """Create an OrganizerSettings from a raw dict, ignoring unknown keys."""
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Config object
# ---------------------------------------------------------------------------

@dataclass
class OrganizerConfig:
    """Full parsed configuration object handed to the organizer core."""

    categories: Dict[str, Dict[str, Any]]
    settings: OrganizerSettings
    app_metadata: AppMetadata = field(default_factory=AppMetadata)

    # Derived lookup: extension (lowercase) → (category, subcategory)
    extension_map: Dict[str, tuple[str, str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._build_extension_map()

    def _build_extension_map(self) -> None:
        """Pre-compute a flat extension → (category, subcategory) dict for O(1) lookup."""
        for cat_name, cat_data in self.categories.items():
            for sub_name, extensions in cat_data.get("subcategories", {}).items():
                if sub_name == "Other":
                    continue  # "Other" is a catch-all, not a direct mapping
                for ext in extensions:
                    self.extension_map[ext.lower()] = (cat_name, sub_name)

    def resolve(self, extension: str) -> tuple[str, str]:
        """
        Return (category, subcategory) for the given file extension.

        Falls back to the top-level uncategorized folder if not found.
        """
        ext = extension.lower().lstrip(".")
        if ext in self.extension_map:
            return self.extension_map[ext]
        return (self.settings.uncategorized_folder, "")


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class ConfigManager:
    """Loads a JSON or YAML config file and produces an OrganizerConfig."""

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

    def __init__(self, config_path: Optional[str | Path] = None) -> None:
        self._path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> OrganizerConfig:
        """Parse the config file and return a fully resolved OrganizerConfig."""
        raw = self._read_file()
        categories    = raw.get("categories", {})
        settings      = OrganizerSettings.from_dict(raw.get("settings", {}))
        app_metadata  = AppMetadata.from_dict(raw.get("app", {}))
        return OrganizerConfig(
            categories=categories,
            settings=settings,
            app_metadata=app_metadata,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_file(self) -> Dict[str, Any]:
        if not self._path.exists():
            raise FileNotFoundError(f"Config file not found: {self._path}")

        suffix = self._path.suffix.lower()
        text = self._path.read_text(encoding="utf-8")

        if suffix == ".json":
            return json.loads(text)
        elif suffix in {".yaml", ".yml"}:
            return self._load_yaml(text)
        else:
            raise ValueError(
                f"Unsupported config format: '{suffix}'. Use .json or .yaml"
            )

    @staticmethod
    def _load_yaml(text: str) -> Dict[str, Any]:
        """
        Lazy-load PyYAML so the project still works if pyyaml is missing
        and the user sticks to JSON configs.
        """
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required for YAML configs.\n"
                "Install it with:  pip install pyyaml"
            ) from exc
        return yaml.safe_load(text) or {}


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def load_config(path: Optional[str | Path] = None) -> OrganizerConfig:
    """Module-level shortcut used by main.py, core.py, and tests."""
    return ConfigManager(path).load()