"""
gui.py — Intelligent File Organizer · Graphical Interface
==========================================================
Built with CustomTkinter for a modern, cross-platform desktop UI.

Launch via:
    python main.py --gui
    python gui.py          (direct)

Requires:
    pip install customtkinter

Architecture
------------
OrganizerApp (CTk)
  ├── HeaderFrame       — Logo, title, theme toggle
  ├── SidebarFrame      — All settings (paths, options, strategy)
  │     ├── PathSection     source / output folder pickers
  │     ├── OptionsSection  preview, recursive, verbose toggles
  │     └── StrategySection duplicate strategy radio buttons
  ├── LogFrame          — Scrollable live log output
  └── FooterFrame       — Run button, progress bar, status label

The organizer runs in a background thread so the UI stays responsive.
Log messages are piped from the organizer's logging system into the
GUI log panel via a thread-safe queue.
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
from pathlib import Path
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Colour palette & constants
# ---------------------------------------------------------------------------

APP_TITLE   = "Intelligent File Organizer"
APP_VERSION = "v1.0.0"
WIN_W, WIN_H = 960, 680
SIDEBAR_W    = 320
CORNER       = 10
PAD          = 16
SMALL_PAD    = 8

# Map logging levels to tag colours used in the log panel
LOG_COLORS = {
    "INFO":     "#4ade80",   # green
    "DEBUG":    "#60a5fa",   # blue
    "WARNING":  "#facc15",   # yellow
    "ERROR":    "#f87171",   # red
    "CRITICAL": "#e879f9",   # magenta
    "PREVIEW":  "#67e8f9",   # cyan — custom prefix
    "MOVED":    "#4ade80",
    "SKIP":     "#facc15",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ---------------------------------------------------------------------------
# Queue-based logging handler (thread-safe bridge → GUI)
# ---------------------------------------------------------------------------

class _QueueHandler(logging.Handler):
    """Pushes log records into a queue so the GUI thread can consume them."""

    def __init__(self, log_queue: queue.Queue) -> None:
        super().__init__()
        self._q = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        self._q.put(record)


# ---------------------------------------------------------------------------
# Reusable section card widget
# ---------------------------------------------------------------------------

class _SectionCard(ctk.CTkFrame):
    """A rounded card with a bold section title and content area."""

    def __init__(self, parent, title: str, **kwargs):
        super().__init__(parent, corner_radius=CORNER, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
            text_color=("gray30", "gray70"),
        ).grid(row=0, column=0, padx=PAD, pady=(PAD, 4), sticky="ew")

        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.grid(row=1, column=0, padx=SMALL_PAD, pady=(0, PAD), sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)

    @property
    def content(self) -> ctk.CTkFrame:
        return self._content


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

class HeaderFrame(ctk.CTkFrame):
    def __init__(self, parent, on_theme_toggle, **kwargs):
        super().__init__(parent, height=56, corner_radius=0, **kwargs)
        self.grid_columnconfigure(1, weight=1)

        # Icon + title
        ctk.CTkLabel(
            self,
            text="🗂️  " + APP_TITLE,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=PAD, pady=PAD, sticky="w")

        # Version badge
        ctk.CTkLabel(
            self,
            text=APP_VERSION,
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
        ).grid(row=0, column=1, padx=0, pady=PAD, sticky="w")

        # Theme toggle
        self._theme_btn = ctk.CTkButton(
            self,
            text="☀  Light",
            width=88,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            command=on_theme_toggle,
        )
        self._theme_btn.grid(row=0, column=2, padx=PAD, pady=PAD)

    def update_theme_label(self, mode: str) -> None:
        self._theme_btn.configure(text="☀  Light" if mode == "dark" else "🌙  Dark")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

class SidebarFrame(ctk.CTkScrollableFrame):
    """Left panel — all settings live here."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, width=SIDEBAR_W, corner_radius=0, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._row = 0

        self._build_path_section()
        self._build_options_section()
        self._build_strategy_section()
        self._build_config_section()

    # ── Path section ───────────────────────────────────────────────────────

    def _build_path_section(self):
        card = self._add_card("📁  Folders")
        c = card.content

        # Source
        ctk.CTkLabel(c, text="Source directory", anchor="w",
                     font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        self.source_var = ctk.StringVar()
        self._source_entry = ctk.CTkEntry(
            c, textvariable=self.source_var, placeholder_text="Select folder…",
            height=34)
        self._source_entry.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(c, text="Browse", width=64, height=34,
                      command=self._pick_source).grid(row=1, column=1)

        # Output
        ctk.CTkLabel(c, text="Output directory  (optional)", anchor="w",
                     font=ctk.CTkFont(size=12)).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(10, 2))
        self.output_var = ctk.StringVar()
        self._output_entry = ctk.CTkEntry(
            c, textvariable=self.output_var,
            placeholder_text="Defaults to source (in-place)", height=34)
        self._output_entry.grid(row=3, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(c, text="Browse", width=64, height=34,
                      command=self._pick_output).grid(row=3, column=1)

        c.grid_columnconfigure(0, weight=1)

    def _pick_source(self):
        d = filedialog.askdirectory(title="Select source directory")
        if d:
            self.source_var.set(d)

    def _pick_output(self):
        d = filedialog.askdirectory(title="Select output directory")
        if d:
            self.output_var.set(d)

    # ── Options section ────────────────────────────────────────────────────

    def _build_options_section(self):
        card = self._add_card("⚙️   Options")
        c = card.content

        self.preview_var   = ctk.BooleanVar(value=True)
        self.recursive_var = ctk.BooleanVar(value=False)
        self.verbose_var   = ctk.BooleanVar(value=False)
        self.logfile_var   = ctk.BooleanVar(value=True)

        options = [
            (self.preview_var,   "Preview mode",
             "Show planned moves without touching files"),
            (self.recursive_var, "Recursive scan",
             "Include files in subdirectories"),
            (self.verbose_var,   "Verbose logging",
             "Show DEBUG-level messages in the log"),
            (self.logfile_var,   "Write log file",
             "Save log to organizer.log alongside source"),
        ]

        for i, (var, label, tooltip) in enumerate(options):
            row_frame = ctk.CTkFrame(c, fg_color="transparent")
            row_frame.grid(row=i, column=0, sticky="ew", pady=2)
            row_frame.grid_columnconfigure(1, weight=1)

            ctk.CTkSwitch(
                row_frame, text="", variable=var, width=44, height=22,
            ).grid(row=0, column=0, padx=(0, 8))

            ctk.CTkLabel(
                row_frame, text=label, anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).grid(row=0, column=1, sticky="w")

            ctk.CTkLabel(
                row_frame, text=tooltip, anchor="w",
                font=ctk.CTkFont(size=11),
                text_color=("gray50", "gray60"),
                wraplength=SIDEBAR_W - 80,
            ).grid(row=1, column=1, sticky="w")

        c.grid_columnconfigure(0, weight=1)

    # ── Duplicate strategy section ─────────────────────────────────────────

    def _build_strategy_section(self):
        card = self._add_card("🔁  Duplicate strategy")
        c = card.content

        self.strategy_var = ctk.StringVar(value="counter")
        strategies = [
            ("counter",   "Counter",   "photo.png  →  photo (1).png"),
            ("timestamp", "Timestamp", "photo.png  →  photo_20240115_143022.png"),
            ("skip",      "Skip",      "Leave duplicate in source, log warning"),
        ]

        for i, (value, label, subtitle) in enumerate(strategies):
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.grid(row=i, column=0, sticky="ew", pady=3)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkRadioButton(
                row,
                text="",
                variable=self.strategy_var,
                value=value,
                width=24,
            ).grid(row=0, column=0, rowspan=2, padx=(0, 8))

            ctk.CTkLabel(
                row, text=label, anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).grid(row=0, column=1, sticky="w")

            ctk.CTkLabel(
                row, text=subtitle, anchor="w",
                font=ctk.CTkFont(size=11),
                text_color=("gray50", "gray60"),
            ).grid(row=1, column=1, sticky="w")

        c.grid_columnconfigure(0, weight=1)

    # ── Config file section ────────────────────────────────────────────────

    def _build_config_section(self):
        card = self._add_card("📄  Config file  (optional)")
        c = card.content
        c.grid_columnconfigure(0, weight=1)

        self.config_var = ctk.StringVar()
        entry = ctk.CTkEntry(
            c, textvariable=self.config_var,
            placeholder_text="Uses built-in config.json by default",
            height=34)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(c, text="Browse", width=64, height=34,
                      command=self._pick_config).grid(row=0, column=1)

    def _pick_config(self):
        f = filedialog.askopenfilename(
            title="Select config file",
            filetypes=[("Config files", "*.json *.yaml *.yml"), ("All files", "*.*")]
        )
        if f:
            self.config_var.set(f)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _add_card(self, title: str) -> _SectionCard:
        card = _SectionCard(self, title=title)
        card.grid(row=self._row, column=0, padx=SMALL_PAD, pady=(0, SMALL_PAD), sticky="ew")
        self._row += 1
        return card

    # ── Public getters ─────────────────────────────────────────────────────

    def get_settings(self) -> dict:
        return {
            "source":    self.source_var.get().strip(),
            "output":    self.output_var.get().strip(),
            "config":    self.config_var.get().strip(),
            "preview":   self.preview_var.get(),
            "recursive": self.recursive_var.get(),
            "verbose":   self.verbose_var.get(),
            "log_file":  self.logfile_var.get(),
            "strategy":  self.strategy_var.get(),
        }


# ---------------------------------------------------------------------------
# Log panel
# ---------------------------------------------------------------------------

class LogFrame(ctk.CTkFrame):
    """Scrollable panel that displays live log output with colour-coded levels."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, corner_radius=CORNER, **kwargs)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Title bar
        title_bar = ctk.CTkFrame(self, height=36, fg_color="transparent")
        title_bar.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(PAD, 0))
        title_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            title_bar,
            text="📋  Log",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            title_bar,
            text="Clear",
            width=56,
            height=26,
            corner_radius=6,
            fg_color="transparent",
            border_width=1,
            command=self.clear,
        ).grid(row=0, column=2)

        # Textbox
        self._box = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Courier", size=12),
            wrap="word",
            state="disabled",
        )
        self._box.grid(row=1, column=0, sticky="nsew", padx=PAD, pady=PAD)

        # Configure colour tags
        for level, color in LOG_COLORS.items():
            self._box._textbox.tag_configure(level, foreground=color)
        self._box._textbox.tag_configure("DIM", foreground="#6b7280")
        self._box._textbox.tag_configure("BOLD", font=("Courier", 12, "bold"))

    def append(self, message: str, level: str = "INFO") -> None:
        """Append a log line, colour-coded by level keyword found in message."""
        self._box.configure(state="normal")

        # Detect the keyword to apply the right colour tag
        tag = "INFO"
        for key in LOG_COLORS:
            if f"[{key}]" in message or key in message.upper():
                tag = key
                break

        self._box._textbox.insert("end", message + "\n", tag)
        self._box.configure(state="disabled")
        self._box._textbox.see("end")

    def append_separator(self, char: str = "─", width: int = 60) -> None:
        self._box.configure(state="normal")
        self._box._textbox.insert("end", char * width + "\n", "DIM")
        self._box.configure(state="disabled")
        self._box._textbox.see("end")

    def clear(self) -> None:
        self._box.configure(state="normal")
        self._box._textbox.delete("1.0", "end")
        self._box.configure(state="disabled")


# ---------------------------------------------------------------------------
# Footer / controls
# ---------------------------------------------------------------------------

class FooterFrame(ctk.CTkFrame):
    def __init__(self, parent, on_run, **kwargs):
        super().__init__(parent, height=64, corner_radius=0, **kwargs)
        self.grid_columnconfigure(1, weight=1)

        self._run_btn = ctk.CTkButton(
            self,
            text="▶   Run Organizer",
            width=160,
            height=40,
            corner_radius=CORNER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=on_run,
        )
        self._run_btn.grid(row=0, column=0, padx=PAD, pady=PAD)

        self._progress = ctk.CTkProgressBar(self, height=8, corner_radius=4)
        self._progress.set(0)
        self._progress.grid(row=0, column=1, padx=PAD, pady=PAD, sticky="ew")

        self._status = ctk.CTkLabel(
            self,
            text="Ready.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60"),
            width=200,
            anchor="e",
        )
        self._status.grid(row=0, column=2, padx=PAD, pady=PAD)

    def set_running(self, running: bool) -> None:
        if running:
            self._run_btn.configure(state="disabled", text="⏳  Running…")
            self._progress.configure(mode="indeterminate")
            self._progress.start()
        else:
            self._run_btn.configure(state="normal", text="▶   Run Organizer")
            self._progress.stop()
            self._progress.configure(mode="determinate")
            self._progress.set(1)

    def set_status(self, text: str, color: str = "") -> None:
        self._status.configure(text=text, text_color=color or ("gray40", "gray60"))


# ---------------------------------------------------------------------------
# Results summary overlay
# ---------------------------------------------------------------------------

class ResultsDialog(ctk.CTkToplevel):
    """Modal-style window shown after a run completes."""

    def __init__(self, parent, result, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("Run Complete")
        self.geometry("400x320")
        self.resizable(False, False)
        self.grab_set()   # Modal
        self.lift()

        mode = "PREVIEW" if result.preview_mode else "LIVE"
        color = "#67e8f9" if result.preview_mode else "#4ade80"

        ctk.CTkLabel(
            self,
            text=f"{'🔍' if result.preview_mode else '✅'}  {mode} Run Complete",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=color,
        ).pack(pady=(24, 8))

        stats = [
            ("Files processed", str(result.total)),
            ("Moved" if not result.preview_mode else "Would move",
             str(result.moved + result.previewed)),
            ("Skipped (duplicate)",   str(result.skipped)),
            ("Errors",                str(result.errors)),
            ("Time",                  f"{result.elapsed_seconds:.2f}s"),
        ]

        table = ctk.CTkFrame(self, corner_radius=CORNER)
        table.pack(padx=24, pady=8, fill="x")

        for i, (label, value) in enumerate(stats):
            row_color = ("gray90", "gray20") if i % 2 == 0 else ("gray85", "gray17")
            row = ctk.CTkFrame(table, fg_color=row_color, corner_radius=0)
            row.pack(fill="x")
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=label, anchor="w",
                         font=ctk.CTkFont(size=12)).grid(
                row=0, column=0, padx=12, pady=6, sticky="w")
            val_color = "#f87171" if label == "Errors" and value != "0" else ""
            ctk.CTkLabel(row, text=value, anchor="e",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=val_color or ("gray10", "gray90")).grid(
                row=0, column=1, padx=12, pady=6, sticky="e")

        ctk.CTkButton(
            self, text="Close", width=120, height=36, command=self.destroy
        ).pack(pady=16)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class OrganizerApp(ctk.CTk):
    """Root window — assembles all frames and wires up interactions."""

    def __init__(self):
        super().__init__()

        self.title(APP_TITLE)
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.minsize(720, 520)

        self._mode = "dark"
        self._log_queue: queue.Queue = queue.Queue()
        self._running = False

        self._build_layout()
        self._install_log_handler()
        self._poll_log_queue()

        # Welcome message
        self._log.append_separator()
        self._log.append(f"  {APP_TITLE} {APP_VERSION}  —  Ready.", "INFO")
        self._log.append("  Select a source folder and press Run.", "INFO")
        self._log.append("  Tip: keep Preview Mode ON for your first run.", "INFO")
        self._log.append_separator()

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Header (full width)
        self._header = HeaderFrame(
            self, on_theme_toggle=self._toggle_theme,
            fg_color=("gray85", "gray17"),
        )
        self._header.grid(row=0, column=0, columnspan=2, sticky="ew")

        # Sidebar
        self._sidebar = SidebarFrame(self, fg_color=("gray90", "gray14"))
        self._sidebar.grid(row=1, column=0, sticky="nsew")

        # Log panel
        self._log = LogFrame(self, fg_color=("gray95", "gray11"))
        self._log.grid(row=1, column=1, sticky="nsew", padx=(0, 0))

        # Footer (full width)
        self._footer = FooterFrame(
            self, on_run=self._on_run,
            fg_color=("gray85", "gray17"),
        )
        self._footer.grid(row=2, column=0, columnspan=2, sticky="ew")

    # ── Theme ──────────────────────────────────────────────────────────────

    def _toggle_theme(self):
        self._mode = "light" if self._mode == "dark" else "dark"
        ctk.set_appearance_mode(self._mode)
        self._header.update_theme_label(self._mode)

    # ── Logging bridge ─────────────────────────────────────────────────────

    def _install_log_handler(self):
        """Attach a queue handler to the organizer's root logger."""
        handler = _QueueHandler(self._log_queue)
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s",
                              datefmt="%H:%M:%S")
        )
        root = logging.getLogger("file_organizer")
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)

    def _poll_log_queue(self):
        """Drain the log queue every 50 ms on the main thread (Tk-safe)."""
        try:
            while True:
                record = self._log_queue.get_nowait()
                msg = logging.Formatter(
                    "%(asctime)s  %(levelname)-8s  %(message)s",
                    datefmt="%H:%M:%S",
                ).format(record)
                self._log.append(msg, record.levelname)
        except queue.Empty:
            pass
        self.after(50, self._poll_log_queue)

    # ── Run logic ──────────────────────────────────────────────────────────

    def _on_run(self):
        if self._running:
            return

        settings = self._sidebar.get_settings()

        if not settings["source"]:
            self._footer.set_status("⚠  Please select a source folder.", "#facc15")
            return

        source = Path(settings["source"])
        if not source.is_dir():
            self._footer.set_status("⚠  Source folder not found.", "#f87171")
            return

        self._running = True
        self._footer.set_running(True)
        self._footer.set_status("Running…", "#67e8f9")
        self._log.append_separator()

        mode_label = "PREVIEW" if settings["preview"] else "LIVE"
        self._log.append(f"  Starting {mode_label} run…", "INFO")

        thread = threading.Thread(target=self._run_worker, args=(settings,), daemon=True)
        thread.start()

    def _run_worker(self, settings: dict):
        """Runs in a background thread — never touches Tkinter widgets directly."""
        import logging as _logging
        from organizer import FileOrganizer

        try:
            kwargs = {
                "source_dir":   settings["source"],
                "preview_mode": settings["preview"],
                "recursive":    settings["recursive"],
                "log_to_file":  settings["log_file"],
            }
            if settings["output"]:
                kwargs["output_dir"] = settings["output"]
            if settings["config"]:
                kwargs["config_path"] = settings["config"]

            if settings["verbose"]:
                _logging.getLogger("file_organizer").setLevel(_logging.DEBUG)

            organizer = FileOrganizer(**kwargs)
            organizer._config.settings.duplicate_strategy = settings["strategy"]
            result = organizer.run()

            # Schedule UI update back on main thread
            self.after(0, self._on_run_complete, result)

        except Exception as exc:
            _logging.getLogger("file_organizer").error(f"Run failed: {exc}")
            self.after(0, self._on_run_error, str(exc))

    def _on_run_complete(self, result):
        self._running = False
        self._footer.set_running(False)

        if result.errors:
            self._footer.set_status(
                f"Done — {result.errors} error(s).", "#f87171")
        elif result.preview_mode:
            self._footer.set_status(
                f"Preview complete — {result.previewed} file(s) would move.", "#67e8f9")
        else:
            self._footer.set_status(
                f"Done — {result.moved} file(s) moved.", "#4ade80")

        self._log.append_separator()
        ResultsDialog(self, result)

    def _on_run_error(self, message: str):
        self._running = False
        self._footer.set_running(False)
        self._footer.set_status(f"Error: {message}", "#f87171")
        self._log.append_separator()


# ---------------------------------------------------------------------------
# Direct launch
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = OrganizerApp()
    app.mainloop()