"""
duplicate_handler.py
--------------------
Resolves filename conflicts when a file already exists at the destination.

Supported strategies
--------------------
counter    → photo.png → photo (1).png → photo (2).png  (Windows Explorer style)
timestamp  → photo.png → photo_20240115_143022.png
skip       → leave the source file in place, log a warning

Design decisions:
  - Strategies are implemented as standalone functions (not classes) because
    they're pure transformations with no shared state — functions are simpler.
  - The resolve() dispatcher is the only public surface, keeping call sites
    clean and strategy changes to a single config key.
  - All path checks are performed here so mover.py stays focused on I/O.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from .logger import get_child_logger

log = get_child_logger("duplicate_handler")

Strategy = Literal["counter", "timestamp", "skip"]

_MAX_COUNTER = 9999  # Sanity cap to avoid infinite loops


# ---------------------------------------------------------------------------
# Public resolver
# ---------------------------------------------------------------------------

def resolve(
    destination: Path,
    strategy: Strategy = "counter",
) -> Optional[Path]:
    """
    Return a safe destination path that does not currently exist.

    Parameters
    ----------
    destination : The originally desired destination path.
    strategy    : How to handle conflicts — 'counter', 'timestamp', or 'skip'.

    Returns
    -------
    A Path that is guaranteed not to exist yet, or None if strategy='skip'.
    """
    if not destination.exists():
        return destination  # No conflict — use as-is

    log.debug(f"Conflict detected for: {destination.name}")

    if strategy == "counter":
        return _counter_strategy(destination)
    elif strategy == "timestamp":
        return _timestamp_strategy(destination)
    elif strategy == "skip":
        log.warning(f"Skipping duplicate: {destination.name}")
        return None
    else:
        raise ValueError(f"Unknown duplicate strategy: '{strategy}'. "
                         f"Valid options: counter, timestamp, skip")


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

def _counter_strategy(destination: Path) -> Path:
    """
    Append an incrementing counter suffix until a free path is found.

    Example: report.pdf → report (1).pdf → report (2).pdf
    """
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent

    for i in range(1, _MAX_COUNTER + 1):
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            log.debug(f"Counter resolved: {destination.name} → {candidate.name}")
            return candidate

    raise RuntimeError(
        f"Could not resolve duplicate after {_MAX_COUNTER} attempts: {destination}"
    )


def _timestamp_strategy(destination: Path) -> Path:
    """
    Append a timestamp suffix to the filename.

    Example: report.pdf → report_20240115_143022.pdf

    If (extremely unlikely) a timestamp collision occurs, falls back to
    appending a counter after the timestamp.
    """
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    candidate = parent / f"{stem}_{ts}{suffix}"
    if not candidate.exists():
        log.debug(f"Timestamp resolved: {destination.name} → {candidate.name}")
        return candidate

    # Sub-second collision — add milliseconds
    ts_ms = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    candidate = parent / f"{stem}_{ts_ms}{suffix}"
    if not candidate.exists():
        return candidate

    # Last resort: delegate to counter
    log.debug("Timestamp collision — falling back to counter strategy")
    return _counter_strategy(candidate)
