#!/usr/bin/env python3
"""
main.py — Intelligent File Organizer CLI
=========================================
Run with no arguments (or --help / -h) to see the full usage guide.

Quick reference:
  python main.py SOURCE_DIR [OPTIONS]
  python main.py --gui
"""

# ---------------------------------------------------------------------------
# Bootstrap must be the very first import — before anything that could fail.
# It detects missing packages and auto-installs them, then re-launches.
# ---------------------------------------------------------------------------
import bootstrap
bootstrap.ensure()

# ---------------------------------------------------------------------------
# Standard library imports (safe after bootstrap)
# ---------------------------------------------------------------------------
from __future__ import annotations

import argparse
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# ANSI colour helpers (Windows 10+, macOS, Linux)
# ---------------------------------------------------------------------------

_RESET   = "\x1b[0m"
_BOLD    = "\x1b[1m"
_DIM     = "\x1b[2m"
_GREEN   = "\x1b[32m"
_CYAN    = "\x1b[36m"
_YELLOW  = "\x1b[33m"
_WHITE   = "\x1b[97m"
_MAGENTA = "\x1b[35m"


def _c(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes only when stdout is a real terminal."""
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + _RESET


# ---------------------------------------------------------------------------
# Help content
# ---------------------------------------------------------------------------

BANNER = r"""
  ______ _ _        ____
 |  ____(_) |      / __ \
 | |__   _| | ___ | |  | |_ __ __ _
 |  __| | | |/ _ \| |  | | '__/ _` |
 | |    | | |  __/| |__| | | | (_| |
 |_|    |_|_|\___| \____/|_|  \__, |
                                __/ |
  Intelligent File Organizer   |___/
"""

# Each entry: (flag_text, kind, description)
# kind controls the badge colour:
#   required / optional / flag / default / choice
FLAG_GROUPS = [
    (
        "Paths",
        _CYAN,
        [
            ("SOURCE_DIR",           "required", "Directory to scan and organise"),
            ("--output,  -o  DIR",   "optional", "Output directory. Defaults to SOURCE_DIR (in-place)"),
            ("--config,  -c  FILE",  "optional", "Custom JSON or YAML config file"),
            ("--log-file     FILE",  "optional", "Log file path  (default: organizer.log in cwd)"),
        ],
    ),
    (
        "Behaviour",
        _GREEN,
        [
            ("--preview,           -p", "flag",    "Dry-run — show planned moves WITHOUT touching files"),
            ("--recursive,         -r", "flag",    "Scan subdirectories recursively"),
            ("--no-log-file",           "flag",    "Console-only logging (skip writing a log file)"),
            ("--verbose,           -v", "flag",    "Enable DEBUG-level output in the console"),
            ("--no-exclude-dash-folders","flag",
             "Disable dash-folder exclusion (scan -Folders normally). Default: exclusion ON"),
        ],
    ),
    (
        "Duplicate strategy  (--duplicate-strategy / -d)",
        _YELLOW,
        [
            ("counter",    "default", "photo.png  →  photo (1).png  →  photo (2).png"),
            ("timestamp",  "choice",  "photo.png  →  photo_20240115_143022.png"),
            ("skip",       "choice",  "Leave the source file in place, log a warning"),
        ],
    ),
    (
        "Interface",
        _MAGENTA,
        [
            ("--gui",      "flag", "Launch the CustomTkinter graphical interface"),
            ("--help, -h", "flag", "Show this help message and exit"),
        ],
    ),
]

EXAMPLES = [
    ("Preview only — no files are moved",
     "python main.py ~/Downloads --preview"),
    ("Organise into a separate folder",
     "python main.py ~/Downloads --output ~/Organized"),
    ("Recursive scan + timestamp on duplicates",
     "python main.py ~/Downloads -r --duplicate-strategy timestamp"),
    ("Disable dash-folder exclusion (scan -Folders normally)",
     "python main.py ~/Downloads --no-exclude-dash-folders"),
    ("Custom config, verbose, no log file",
     "python main.py ~/Downloads --config my_rules.json -v --no-log-file"),
    ("Open the graphical interface",
     "python main.py --gui"),
]

KIND_LABEL = {
    "required": "[required]",
    "optional": "[optional]",
    "flag":     "[flag]    ",
    "default":  "[default] ",
    "choice":   "[choice]  ",
}
KIND_COLOR = {
    "required": _YELLOW,
    "optional": _DIM,
    "flag":     _DIM,
    "default":  _GREEN,
    "choice":   _DIM,
}


def print_help() -> None:
    """Print the coloured help/usage screen to stdout."""

    print(_c(BANNER, _CYAN, _BOLD))
    print(_c("  Automatically sorts messy directories into clean, categorized structures.", _DIM))
    print()

    print(_c("USAGE", _WHITE, _BOLD))
    print(f"  python main.py {_c('SOURCE_DIR', _CYAN)} [OPTIONS]")
    print(f"  python main.py {_c('--gui', _MAGENTA)}")
    print()

    print(_c("FLAGS & OPTIONS", _WHITE, _BOLD))
    for title, color, flags in FLAG_GROUPS:
        print(f"\n  {_c('▸ ' + title, color, _BOLD)}")
        for flag_text, kind, desc in flags:
            badge    = _c(KIND_LABEL[kind], KIND_COLOR[kind])
            flag_col = _c(f"{flag_text:<34}", color)
            print(f"    {flag_col}  {badge}  {desc}")

    print()
    print(_c("DASH-FOLDER EXCLUSION", _WHITE, _BOLD))
    print(
        f"\n  {_c('Enabled by default.', _GREEN)}  "
        f"Folders whose names start with {_c('\"-\"', _YELLOW)} are moved intact\n"
        f"  to the {_c('Excluded/', _CYAN)} output folder instead of being scanned.\n"
        f"\n  Examples: {_c('-Personal/', _CYAN)}  {_c('-Archive/', _CYAN)}  {_c('-Old Files/', _CYAN)}"
        f"\n\n  Input:"
        f"\n    {_c('Downloads/', _DIM)}"
        f"\n      ├── report.pdf"
        f"\n      ├── photo.png"
        f"\n      └── {_c('-Personal/', _YELLOW)}  ← not scanned"
        f"\n\n  Output:"
        f"\n    {_c('Documents/PDF/', _DIM)}report.pdf"
        f"\n    {_c('Photos/PNG/',    _DIM)}photo.png"
        f"\n    {_c('Excluded/',      _CYAN)}{_c('-Personal/', _YELLOW)}  ← moved as-is"
    )

    print()
    print(_c("EXAMPLES", _WHITE, _BOLD))
    for label, cmd in EXAMPLES:
        print(f"\n  {_c('# ' + label, _DIM)}")
        print(f"  {_c(cmd, _CYAN)}")

    print()
    print(_c("─" * 68, _DIM))
    print(_c("  Tip: always run --preview first on important directories.", _YELLOW))
    print(_c("  See README.md for full documentation and plugin guide.", _DIM))
    print()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """
    Build the argparse parser with add_help=False so we can render our own
    coloured help screen instead of argparse's plain output.
    """
    parser = argparse.ArgumentParser(prog="file-organizer", add_help=False)

    # Positional
    parser.add_argument("source",                  nargs="?", default=None)

    # Paths
    parser.add_argument("--output",    "-o",       default=None)
    parser.add_argument("--config",    "-c",       default=None)
    parser.add_argument("--log-file",              default=None)

    # Behaviour flags
    parser.add_argument("--preview",   "-p",       action="store_true", default=False)
    parser.add_argument("--recursive", "-r",       action="store_true", default=False)
    parser.add_argument("--no-log-file",           action="store_true", default=False)
    parser.add_argument("--verbose",   "-v",       action="store_true", default=False)

    # Dash-folder exclusion toggle (default=None → "use config value")
    # Presence of --no-exclude-dash-folders disables the feature.
    parser.add_argument(
        "--no-exclude-dash-folders",
        dest="disable_dash_exclusion",
        action="store_true",
        default=False,
        help="Disable dash-folder exclusion; scan -folders normally.",
    )

    # Duplicate strategy
    parser.add_argument(
        "--duplicate-strategy", "-d",
        choices=["counter", "timestamp", "skip"],
        default=None,
    )

    # Interface
    parser.add_argument("--gui",                   action="store_true", default=False)
    parser.add_argument("--help", "-h",            action="store_true", default=False)

    return parser


# ---------------------------------------------------------------------------
# GUI launcher
# ---------------------------------------------------------------------------

def launch_gui() -> int:
    """Import and start the CustomTkinter GUI. Returns exit code."""
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        print(_c("\n  ERROR: customtkinter is not installed.", _YELLOW, _BOLD))
        print("  Install it with:\n")
        print(_c("    pip install customtkinter", _CYAN))
        print()
        return 1

    from gui import OrganizerApp
    app = OrganizerApp()
    app.mainloop()
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # ── No arguments or explicit --help ───────────────────────────────────
    if args.help or (args.source is None and not args.gui):
        print_help()
        return 0

    # ── GUI mode ──────────────────────────────────────────────────────────
    if args.gui:
        return launch_gui()

    # ── CLI mode ──────────────────────────────────────────────────────────
    source = Path(args.source)
    if not source.exists():
        print(_c(f"\n  ERROR: Directory does not exist: {source}\n", _YELLOW),
              file=sys.stderr)
        return 1
    if not source.is_dir():
        print(_c(f"\n  ERROR: Path is not a directory: {source}\n", _YELLOW),
              file=sys.stderr)
        return 1

    import logging
    from organizer import FileOrganizer

    # Build constructor kwargs
    kwargs: dict = {
        "source_dir":            source,
        "preview_mode":          args.preview,
        "recursive":             args.recursive,
        "log_to_file":           not args.no_log_file,
        # None = use config default (True); False = feature disabled
        "exclude_dash_folders":  False if args.disable_dash_exclusion else None,
    }

    if args.output:
        kwargs["output_dir"] = Path(args.output)
    if args.config:
        kwargs["config_path"] = Path(args.config)
    if args.log_file:
        kwargs["log_file"] = Path(args.log_file)

    if args.verbose:
        logging.getLogger("file_organizer").setLevel(logging.DEBUG)

    try:
        organizer = FileOrganizer(**kwargs)
        if args.duplicate_strategy:
            organizer._config.settings.duplicate_strategy = args.duplicate_strategy

        result = organizer.run()
        result.print_summary()
        return 1 if (result.errors + result.folders_errored) > 0 else 0

    except FileNotFoundError as exc:
        print(_c(f"\n  ERROR: {exc}\n", _YELLOW), file=sys.stderr)
        return 1
    except PermissionError as exc:
        print(_c(f"\n  ERROR: Insufficient permissions — {exc}\n", _YELLOW),
              file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n  Aborted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())