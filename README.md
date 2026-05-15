# 🗂️ Intelligent File Organizer

> Ever opened your Downloads folder and found thousands of random PDFs, screenshots, ZIPs, installers, and school files mixed together?
>
> Intelligent File Organizer automatically transforms chaotic directories into clean, categorized structures — while protecting important folders, preventing accidental file scattering, and giving you full control through both CLI and GUI modes.

A modular, production-ready Python tool that automatically sorts messy directories into clean, categorized folder structures — with an architecture designed to grow into an AI-powered personal file management system.

---

## ✨ Features

| Feature                                             | Status                |
| --------------------------------------------------- | --------------------- |
| Extension-based categorization                      | ✅                     |
| MIME-type fallback                                  | ✅                     |
| Duplicate handling (counter / timestamp / skip)     | ✅                     |
| Preview / dry-run mode                              | ✅                     |
| Recursive directory scanning                        | ✅                     |
| Dash-folder exclusion (`-FolderName` → `Excluded/`) | ✅                     |
| JSON & YAML config files                            | ✅                     |
| Structured logging (console + rotating file)        | ✅                     |
| Custom categorization plugins                       | ✅                     |
| Dependency auto-installer (bootstrap)               | ✅                     |
| CustomTkinter GUI                                   | ✅                     |
| Version management & update notifications           | ✅                     |
| CLI update notice (startup check)                   | ✅                     |
| GUI update dialog (non-blocking, background)        | ✅                     |
| AI classification hook                              | 🔜 plug-in ready      |
| Real-time folder monitoring (watchdog)              | 🔜 Phase 2            |
| SQLite file history database                        | 🔜 Phase 3            |
| AI / OCR smart sorting                              | 🔜 Phase 4 (optional) |
| EXE auto-updater                                    | 🔜 Future             |

---

## 🚀 Why Use It?

* ⚡ Organize thousands of files in minutes
* 🛡️ Protect important grouped folders automatically
* 👀 Preview all actions before moving files
* 🖥️ Use either CLI or modern GUI mode
* 🔄 Automatic dependency installation support
* 🧠 Built for future AI-powered organization
* 📂 Prevent accidental folder scattering

---

## 🚀 Quick Start

### Download Latest Release

[Download Latest Source Code](https://github.com/YTUpronicGamergaming/IntelligentFileOrg/releases/tag/v1.1.0)

```bash
# 1. Clone / download the project
git clone https://github.com/YTUpronicGamergaming/IntelligentFileOrg.git

cd intelligent_file_organizer

# 2. (Optional) Create virtual environment
py -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Preview what will happen — no files moved
py main.py /path/to/your/downloads --preview

# 5. Run for real
py main.py /path/to/your/downloads

# 6. Organise into a separate output folder
py main.py ~/Downloads --output ~/Organized

# 7. Launch GUI
py main.py --gui
```

If required dependencies are missing, the built-in bootstrapper can automatically install them from `requirements.txt` and retry execution automatically.

---

## 📖 CLI Reference

```bash
py main.py SOURCE_DIR [OPTIONS]
```

### Options

* `--output, -o DIR`
  Output directory (defaults to SOURCE_DIR)

* `--config, -c FILE`
  Custom JSON or YAML config file

* `--preview, -p`
  Dry-run: show planned moves without executing

* `--recursive, -r`
  Scan subdirectories recursively

* `--duplicate-strategy`
  `counter | timestamp | skip`

* `--no-log-file`
  Console-only logging

* `--log-file FILE`
  Custom log file path

* `--verbose, -v`
  Enable DEBUG output

* `--no-exclude-dash-folders`
  Disable dash-folder exclusion and scan `-Folders` normally

* `--gui`
  Launch CustomTkinter GUI

---

## 🏗️ Project Architecture

```text
intelligent_file_organizer/

│
├── main.py                    ← CLI entry point (argparse + update notice)
├── gui.py                     ← CustomTkinter GUI (update dialog, log panel)
├── bootstrap.py               ← Dependency auto-installer
├── config.json                ← Extension mappings, settings, app metadata
├── requirements.txt
│
└── organizer/
    ├── __init__.py
    ├── core.py
    ├── config_manager.py
    ├── version_controller.py
    ├── logger.py
    ├── scanner.py
    ├── categorizer.py
    ├── duplicate_handler.py
    └── mover.py

tests/
    └── test_organizer.py
```

---

## 🔄 Update Notifications

The app automatically checks GitHub releases for newer versions.

### Features

* Background update checking
* GUI update dialog
* CLI startup notification
* Semantic version comparison
* Silent offline fallback
* Non-blocking GUI behavior

### GUI Behavior

When a new version is available:

* Shows current vs latest version
* Provides:

  * **[Update Now]**
  * **[Later]**
* Opens GitHub releases page directly

### CLI Example

```text
🔔 UPDATE AVAILABLE

Current Version : v1.1.0
Latest Version  : v1.2.0

Download:
https://github.com/YTUpronicGamergaming/IntelligentFileOrg/releases
```

### Future Plans

Planned future support includes:

* Automatic `.exe` downloads
* In-app updater
* Silent updates
* Rollback support

---

## 🚫 Excluded Dash Folders

Folders beginning with `-` are treated as protected folders.

Examples:

* `-Personal`
* `-Archive`
* `-School`

Behavior:

* excluded from recursive scanning
* contents remain untouched internally
* moved intact as complete folders
* configurable in GUI, CLI, and config

This prevents important grouped folders from being accidentally scattered during organization.

---

## ⚙️ Configuration

```json
{
  "app": {
    "name": "Intelligent File Organizer",
    "version": "1.1.0",
    "github_repo": "YTUpronicGamergaming/IntelligentFileOrg"
  },

  "settings": {
    "duplicate_strategy": "counter",
    "recursive": false,
    "preview_mode": false,
    "skip_hidden_files": true,
    "exclude_dash_folders": true,
    "excluded_folder_name": "Excluded",
    "uncategorized_folder": "Uncategorized"
  }
}
```

YAML format is also supported.

---

## 🧪 Running Tests

```bash
# All tests
py -m pytest tests/ -v

# Coverage
py -m pytest tests/ --cov=organizer --cov-report=term-missing
```

---

## 🛣️ Development Roadmap

### Phase 1 — Core ✅

* [x] Extension + MIME categorization
* [x] Duplicate handling
* [x] Recursive scanning
* [x] Preview mode
* [x] Dash-folder exclusion
* [x] Plugin architecture
* [x] Dependency bootstrapper

### Phase 1.1 — GUI & Versioning ✅

* [x] CustomTkinter GUI
* [x] Version controller
* [x] GUI update dialog
* [x] CLI update notifications
* [x] Semantic version comparison

### Phase 2 — Monitoring

* [ ] Real-time folder watcher
* [ ] Background monitoring service
* [ ] Task Scheduler integration

### Phase 3 — Database & History

* [ ] SQLite history database
* [ ] Undo system
* [ ] File metadata indexing
* [ ] Search system

### Phase 4 — AI Features (Optional)

* [ ] OCR support
* [ ] Receipt/document detection
* [ ] AI semantic tagging
* [ ] Smart suggestions

### Phase 5 — EXE Auto-Updater

* [ ] Silent `.exe` updates
* [ ] In-app updater UI
* [ ] Rollback support
* [ ] Scheduled update checks

---

## 🔒 Security Considerations

* The organizer never deletes files — it only moves them.
* Always run `--preview` first on important directories.
* Dash-folders are handled as intact folder units.
* File permissions are preserved by `shutil.move`.
* The update checker only makes a small HTTPS request to GitHub releases.
* No local file data is uploaded or transmitted.

---

## 📜 License

MIT — free to use, modify, and distribute.
