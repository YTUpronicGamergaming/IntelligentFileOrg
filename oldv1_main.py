#!/usr/bin/env python3
"""
main.py — Intelligent File Organizer CLI
=========================================
Entry point for running the organizer from the command line.

Usage examples
--------------
# Preview what would happen (no files moved)
python main.py /path/to/downloads --preview

# Organise into a separate output folder
python main.py /path/to/downloads --output /path/to/organized

# Recursive scan + custom config
python main.py /path/to/downloads --recursive --config my_config.json

# Live run with file logging disabled
python main.py /path/to/downloads --no-log-file
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="file-organizer",
        description=(
            "Intelligent File Organizer — automatically sorts files into\n"
            "categorized folders based on extension and MIME type.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py ~/Downloads --preview
  python main.py ~/Downloads --output ~/Organized --recursive
  python main.py ~/Downloads --config custom.json --duplicate-strategy timestamp
        """,
    )

    # --- Required / positional ---
    parser.add_argument(
        "source",
        metavar="SOURCE_DIR",
        help="Directory to scan and organise.",
    )

    # --- Optional paths ---
    parser.add_argument(
        "--output", "-o",
        metavar="OUTPUT_DIR",
        default=None,
        help=(
            "Where to place the organised folders. "
            "Defaults to SOURCE_DIR (organises in-place)."
        ),
    )
    parser.add_argument(
        "--config", "-c",
        metavar="CONFIG_FILE",
        default=None,
        help="Path to a custom JSON or YAML config file.",
    )
    parser.add_argument(
        "--log-file",
        metavar="LOG_FILE",
        default=None,
        help="Path for the log file (default: organizer.log in current directory).",
    )

    # --- Behaviour flags ---
    parser.add_argument(
        "--preview", "-p",
        action="store_true",
        default=False,
        help="Show what would happen without moving any files.",
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        default=False,
        help="Scan subdirectories recursively.",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        default=False,
        help="Disable writing logs to a file (console only).",
    )

    # --- Duplicate strategy ---
    parser.add_argument(
        "--duplicate-strategy", "-d",
        choices=["counter", "timestamp", "skip"],
        default=None,
        help=(
            "How to handle filename conflicts at the destination. "
            "counter (default): photo.png → photo (1).png. "
            "timestamp: photo.png → photo_20240115_143022.png. "
            "skip: leave duplicate files in place."
        ),
    )

    # --- Verbosity ---
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable DEBUG-level output.",
    )

    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Parse args, run the organizer, print summary. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args()

    # Validate source directory early for a friendly error message
    source = Path(args.source)
    if not source.exists():
        print(f"ERROR: Source directory does not exist: {source}", file=sys.stderr)
        return 1
    if not source.is_dir():
        print(f"ERROR: Source path is not a directory: {source}", file=sys.stderr)
        return 1

    # Lazy import so the CLI help text renders instantly
    import logging
    from organizer import FileOrganizer

    # Build keyword arguments for FileOrganizer
    kwargs: dict = {
        "source_dir":   source,
        "preview_mode": args.preview,
        "recursive":    args.recursive,
        "log_to_file":  not args.no_log_file,
    }

    if args.output:
        kwargs["output_dir"] = Path(args.output)
    if args.config:
        kwargs["config_path"] = Path(args.config)
    if args.log_file:
        kwargs["log_file"] = Path(args.log_file)

    # Adjust log level
    if args.verbose:
        logging.getLogger("file_organizer").setLevel(logging.DEBUG)

    try:
        organizer = FileOrganizer(**kwargs)

        # Apply CLI duplicate strategy override after construction
        if args.duplicate_strategy:
            organizer._config.settings.duplicate_strategy = args.duplicate_strategy

        result = organizer.run()
        result.print_summary()

        # Non-zero exit if there were errors
        return 1 if result.errors > 0 else 0

    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except PermissionError as exc:
        print(f"ERROR: Insufficient permissions — {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAborted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
