"""
bootstrap.py
------------
Dependency auto-installer that runs before the main application starts.

Problem it solves
-----------------
A user downloads the project and runs `python main.py` without having read
the README or run `pip install -r requirements.txt`. Instead of a cold
traceback, they get a friendly install prompt and an automatic retry.

How it works
------------
1. main.py calls `bootstrap.ensure()` at the very top, before any other
   imports that could fail.
2. `ensure()` tries to import each known optional package.
3. If anything is missing, it installs from requirements.txt via subprocess.
4. To prevent an infinite install → crash → install loop, it sets an
   environment variable (IFO_BOOTSTRAPPED) before re-launching.
5. If the re-launched process still fails, it exits with a clear message.

Cross-platform notes
--------------------
- Uses `subprocess.run` + `sys.exit` rather than `os.execve` because that
  works identically on Windows, macOS, and Linux.
- The subprocess inherits all environment variables including IFO_BOOTSTRAPPED,
  which prevents the guard from being lost across the process boundary.
- pip output is shown in real time (no capture) so users can see progress.

What it does NOT do
-------------------
- It never auto-installs dev-only packages (pytest, pytest-cov).
- It never runs pip with --user or sudo — it respects the active venv.
- It does not modify requirements.txt or any project file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Environment variable used as a one-shot guard against re-entry.
# Set to "1" immediately before re-launching; detected on the next run.
_GUARD_ENV_VAR = "IFO_BOOTSTRAPPED"

# Path to the requirements file, relative to this script's location.
_REQ_PATH = Path(__file__).parent / "requirements.txt"

# Packages to check at startup.
# Format: { pip_package_name: (python_import_name, condition_to_check) }
#
# condition_to_check is a callable that returns True when the package is
# actually needed — lets us skip GUI deps for pure CLI runs.
_PACKAGES: Dict[str, Tuple[str, object]] = {
    "packaging":     ("packaging",     lambda: True),               # version comparison — always needed
    "customtkinter": ("customtkinter", lambda: "--gui" in sys.argv),
    "pyyaml":        ("yaml",          lambda: _yaml_config_requested()),
}


def _yaml_config_requested() -> bool:
    """Return True if the user passed a .yaml or .yml config path."""
    for i, arg in enumerate(sys.argv):
        if arg in ("--config", "-c") and i + 1 < len(sys.argv):
            return sys.argv[i + 1].lower().endswith((".yaml", ".yml"))
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ensure() -> None:
    """
    Check that all needed packages are installed; install and re-launch if not.

    This is a no-op when everything is already satisfied.
    Call this at the very top of main.py, before any other imports.
    """
    missing = _find_missing()
    if not missing:
        return  # All good — fast path

    # If we already ran an install pass, don't loop again
    if os.environ.get(_GUARD_ENV_VAR) == "1":
        _fatal(
            "One or more packages are still missing after installation.\n"
            f"  Missing: {', '.join(missing)}\n"
            "  Please install manually:\n"
            f"    pip install -r {_REQ_PATH}"
        )

    _print_banner(missing)
    _install()
    _relaunch()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_missing() -> List[str]:
    """Return pip package names for packages that cannot currently be imported."""
    missing: List[str] = []
    for pip_name, (import_name, condition) in _PACKAGES.items():
        # Only check packages that are actually needed right now
        if callable(condition) and not condition():
            continue
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    return missing


def _print_banner(missing: List[str]) -> None:
    sep = "─" * 60
    print(f"\n{sep}")
    print("  Intelligent File Organizer — Dependency Installer")
    print(sep)
    print(f"  Missing package(s): {', '.join(missing)}")
    print(f"  Installing from: {_REQ_PATH.name}")
    print(sep)


def _install() -> None:
    """Run pip install -r requirements.txt; exit on failure."""
    if not _REQ_PATH.exists():
        _fatal(
            f"requirements.txt not found at:\n  {_REQ_PATH}\n"
            "Cannot auto-install. Please run:\n"
            "  pip install customtkinter pyyaml"
        )

    print("\n  Running: pip install -r requirements.txt\n")

    # Stream pip output to the terminal in real time (no capture)
    result = subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "-r", str(_REQ_PATH),
            "--no-warn-script-location",
        ]
    )

    if result.returncode != 0:
        _fatal(
            f"pip install exited with code {result.returncode}.\n"
            "Please install dependencies manually:\n"
            f"  pip install -r {_REQ_PATH}"
        )

    print("\n  Installation complete.")


def _relaunch() -> None:
    """Re-execute the current script with the bootstrap guard set."""
    print("  Restarting application...\n")

    env = os.environ.copy()
    env[_GUARD_ENV_VAR] = "1"

    # subprocess.run + sys.exit works identically on Windows, macOS, Linux.
    # We do NOT use os.execve here because on Windows it spawns a child rather
    # than truly replacing the process, making signal/exit-code propagation
    # unreliable. subprocess.run is explicit and portable.
    result = subprocess.run(
        [sys.executable] + sys.argv,
        env=env,
    )
    sys.exit(result.returncode)


def _fatal(message: str) -> None:
    """Print an error and exit with code 1."""
    print(f"\n  [Bootstrap] ERROR\n  {message}\n", file=sys.stderr)
    sys.exit(1)