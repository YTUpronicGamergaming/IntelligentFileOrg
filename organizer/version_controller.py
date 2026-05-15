"""
version_controller.py
---------------------
Single source of truth for version management and GitHub update checking.

Responsibilities
----------------
- Read the local version from OrganizerConfig.app_metadata (config.json).
- Fetch the latest release tag from GitHub's public REST API.
- Compare versions semantically using the `packaging` library.
- Expose simple, typed results for both CLI and GUI consumers.
- Never crash: all network operations are wrapped with timeouts and broad
  exception handling so offline users always get a graceful fallback.

Usage
-----
    from organizer.version_controller import VersionController
    from organizer.config_manager import load_config

    vc = VersionController(load_config())

    # Synchronous check (used in CLI — short timeout so it never blocks long)
    result = vc.check()
    if result.available:
        print(f"Update available: {result.local} → {result.latest}")

    # Non-blocking async check (used in GUI)
    vc.check_async(callback=my_callback_fn)   # callback(result) on completion

Architecture notes
------------------
- VersionController is intentionally stateless between calls so it is safe
  to instantiate once and reuse across threads.
- check_async() creates a daemon thread so it never blocks app shutdown.
- The GitHub API returns the tag_name field as the canonical version string
  (e.g. "v1.2.0"). We strip the leading "v" before parsing to keep the
  comparison consistent with packaging.version.Version.
- packaging.version.Version handles pre-release, post-release, and dev
  suffixes correctly (e.g. 1.2.0a1 < 1.2.0). Plain integers work too.

Future auto-updater hooks
-------------------------
UpdateResult carries the release_url and asset_download_url fields so a
future auto-updater can retrieve the right download without a second API hit:

    result = vc.check()
    if result.available and result.asset_download_url:
        download_and_install(result.asset_download_url)
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Optional

from .config_manager import AppMetadata, OrganizerConfig

log = logging.getLogger("file_organizer.version")

# Network timeout in seconds — short enough to not noticeably block startup.
_TIMEOUT_SECONDS = 4

# User-Agent header required by GitHub API policy.
_USER_AGENT = "IntelligentFileOrganizer-UpdateChecker/1"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class UpdateResult:
    """
    Outcome of a single version check.

    Attributes
    ----------
    available           : True when a newer version exists on GitHub.
    local               : Local version string (e.g. "1.1.0").
    latest              : Latest GitHub version string, or None if the check failed.
    release_url         : URL to the GitHub releases page (always populated).
    asset_download_url  : Direct download URL for the first release asset, or None.
    error               : Human-readable error message when the check failed.
    checked             : True when the GitHub API was actually reached.
    """

    available: bool = False
    local: str = "unknown"
    latest: Optional[str] = None
    release_url: str = ""
    asset_download_url: Optional[str] = None
    error: Optional[str] = None
    checked: bool = False

    @property
    def local_tag(self) -> str:
        """Return local version with a leading 'v' prefix."""
        return self.local if self.local.startswith("v") else f"v{self.local}"

    @property
    def latest_tag(self) -> str:
        """Return latest version with a leading 'v' prefix, or 'unknown'."""
        if not self.latest:
            return "unknown"
        return self.latest if self.latest.startswith("v") else f"v{self.latest}"


# ---------------------------------------------------------------------------
# Version controller
# ---------------------------------------------------------------------------

class VersionController:
    """
    Manages version comparison and GitHub release update checks.

    Parameters
    ----------
    config : OrganizerConfig — provides local version and GitHub URLs via
             the app_metadata field.
    """

    def __init__(self, config: OrganizerConfig) -> None:
        self._meta: AppMetadata = config.app_metadata

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_local_version(self) -> str:
        """Return the local version string as stored in config.json."""
        return self._meta.version

    def get_latest_github_version(self) -> Optional[str]:
        """
        Fetch the latest release tag from GitHub.

        Returns the version string (e.g. "1.2.0") on success, or None on any
        network / parse failure.
        """
        try:
            raw_tag = self._fetch_latest_tag()
            if raw_tag:
                return raw_tag.lstrip("v")
            return None
        except Exception as exc:
            log.debug(f"Version check failed: {exc}")
            return None

    def is_update_available(self) -> tuple[bool, str, Optional[str]]:
        """
        Compare local vs latest GitHub version.

        Returns
        -------
        (available, local_version, latest_version)

        available is False when the check fails or when already up-to-date.
        """
        local   = self.get_local_version()
        latest  = self.get_latest_github_version()

        if not latest:
            return (False, local, None)

        try:
            from packaging.version import Version  # type: ignore
            newer = Version(latest) > Version(local)
            return (newer, local, latest)
        except Exception as exc:
            log.debug(f"Version comparison failed: {exc}")
            return (False, local, latest)

    def check(self) -> UpdateResult:
        """
        Perform a full update check and return a structured UpdateResult.

        This is a synchronous call — use check_async() for non-blocking checks.
        """
        local = self.get_local_version()
        release_url = self._meta.github_releases_url

        try:
            payload = self._fetch_release_payload()
        except Exception as exc:
            msg = str(exc)
            log.debug(f"Update check skipped: {msg}")
            return UpdateResult(
                local=local,
                release_url=release_url,
                error=msg,
                checked=False,
            )

        raw_tag  = (payload.get("tag_name") or "").lstrip("v")
        html_url = payload.get("html_url") or release_url
        assets   = payload.get("assets") or []

        # First asset download URL (future auto-updater hook)
        asset_url: Optional[str] = None
        for asset in assets:
            dl = asset.get("browser_download_url")
            if dl:
                asset_url = dl
                break

        available = False
        error: Optional[str] = None

        if raw_tag:
            try:
                from packaging.version import Version  # type: ignore
                available = Version(raw_tag) > Version(local)
            except Exception as exc:
                error = f"Version parse error: {exc}"
                log.debug(error)
        else:
            error = "Could not parse tag_name from GitHub response."

        result = UpdateResult(
            available=available,
            local=local,
            latest=raw_tag or None,
            release_url=html_url,
            asset_download_url=asset_url,
            error=error,
            checked=True,
        )

        if available:
            log.info(
                f"Update available: {result.local_tag} → {result.latest_tag}  "
                f"({release_url})"
            )
        elif raw_tag:
            log.debug(f"Up to date ({result.local_tag}). Latest: {result.latest_tag}")

        return result

    def check_async(
        self,
        callback: Callable[[UpdateResult], None],
    ) -> None:
        """
        Run check() in a daemon background thread and call callback(result)
        when done.

        The callback is invoked from the worker thread, NOT the main thread.
        GUI consumers must use `self.after(0, ...)` or similar to marshal
        back to the main thread before touching any widget.

        Example (inside a Tkinter/CTk app):
            def _on_result(result: UpdateResult):
                self.after(0, self._show_update_dialog, result)
            vc.check_async(_on_result)
        """
        def _worker():
            result = self.check()
            try:
                callback(result)
            except Exception as exc:
                log.debug(f"Update check callback raised: {exc}")

        t = threading.Thread(target=_worker, daemon=True, name="update-checker")
        t.start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_release_payload(self) -> dict:
        """
        Hit the GitHub releases/latest API and return the parsed JSON payload.

        Raises on any network, HTTP, or JSON error so callers can handle
        uniformly.
        """
        url = self._meta.github_api_latest
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            raw = resp.read()
        return json.loads(raw)

    def _fetch_latest_tag(self) -> Optional[str]:
        """Return just the raw tag_name from the GitHub API, or None."""
        payload = self._fetch_release_payload()
        return payload.get("tag_name")