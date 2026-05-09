# 🗂️ Intelligent File Organizer

> Ever opened your Downloads folder and found thousands of random PDFs, screenshots, ZIPs, installers, and school files mixed together?
>
> Intelligent File Organizer automatically transforms chaotic directories into clean, categorized structures — while protecting important folders, preventing accidental file scattering, and giving you full control through both CLI and GUI modes.

A modular, production-ready Python tool that automatically sorts messy directories into clean, categorized folder structures — with an architecture designed to grow into an AI-powered personal file management system.

---

## ✨ Features

| Feature                                         | Status           |
| ----------------------------------------------- | ---------------- |
| Extension-based categorization                  | ✅                |
| MIME-type fallback                              | ✅                |
| Duplicate handling (counter / timestamp / skip) | ✅                |
| Preview / dry-run mode                          | ✅                |
| Recursive directory scanning                    | ✅                |
| Dash-folder exclusion system (`-FolderName`)    | ✅                |
| Folder-preserving moves                         | ✅                |
| JSON & YAML config files                        | ✅                |
| Structured logging (console + rotating file)    | ✅                |
| Automatic dependency bootstrapper               | ✅                |
| GUI toggle support                              | ✅                |
| CLI toggle support                              | ✅                |
| Custom categorization plugins                   | ✅                |
| AI classification hook                          | 🔜 plug-in ready |
| Real-time folder monitoring (watchdog)          | 🔜               |
| SQLite file history database                    | 🔜               |
| GUI (CustomTkinter)                             | 🔜 / in progress |

---

## 🚀 Why Use It?

* ⚡ Organize thousands of files in minutes
* 🛡️ Protect important folders with dash-folder exclusion
* 👀 Preview changes before moving anything
* 🧠 Built for future AI-powered classification
* 🖥️ Includes both CLI and modern CustomTkinter GUI support
* 🔄 Automatically installs missing dependencies
* 📂 Keeps special folders intact instead of breaking them apart

---

## 🚀 Quick Start

[Download Latest Source Code](https://github.com/YTUpronicGamergaming/IntelligentFileOrg/archive/refs/heads/main.zip)

[Download Latest Release](https://github.com/YTUpronicGamergaming/IntelligentFileOrg/releases/latest) *Not yet available*

```bash
# 1. Clone or download the project
cd intelligent_file_organizer

# 2. (Optional) Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Preview what will happen — no files moved
python main.py /path/to/your/folder --preview

# 5. Run for real
python main.py /path/to/your/folder

# 6. Run with dash-folder exclusion disabled
python main.py /path/to/your/folder --no-exclude-dash-folders

# 7. Launch the GUI
python gui.py
```

If required dependencies are missing, the built-in bootstrapper can automatically install them from `requirements.txt` and retry execution automatically.

---

## 📖 CLI Reference

```bash
python main.py SOURCE_DIR [OPTIONS]
```

### Options

* `--output, -o DIR`
  Output directory. Defaults to `SOURCE_DIR`.

* `--config, -c FILE`
  Custom JSON or YAML config file.

* `--preview, -p`
  Dry-run mode: show planned moves without executing them.

* `--recursive, -r`
  Scan subdirectories recursively.

* `--ignore-dash-folders / --no-exclude-dash-folders`
  Controls whether folders beginning with `-` are excluded from recursive scanning and moved as intact folders instead.
  Default: enabled.

* `--duplicate-strategy`
  `counter | timestamp | skip` (default: `counter`)

* `--no-log-file`
  Console-only logging.

* `--log-file FILE`
  Custom log file path.

* `--verbose, -v`
  Enable DEBUG output.

### Examples

```bash
python main.py ~/Downloads --preview
python main.py ~/Downloads --output ~/Organized
python main.py ~/Downloads --no-exclude-dash-folders
python main.py ~/Downloads --recursive
```

---

## 🏗️ Project Architecture

```text
intelligent_file_organizer/
│
├── main.py                    ← CLI entry point (argparse)
├── gui.py                     ← CustomTkinter GUI entry point
├── bootstrap.py               ← Optional dependency bootstrapper
├── config.json                ← Default extension mappings & settings
├── requirements.txt
│
└── organizer/                 ← Core library (importable as a package)
    ├── __init__.py            ← Exports FileOrganizer
    ├── core.py                ← Façade orchestrator — wires everything together
    ├── config_manager.py      ← JSON/YAML config loading → OrganizerConfig
    ├── logger.py              ← Shared logger (console + rotating file)
    ├── scanner.py             ← Directory traversal → FileInfo / DashFolderInfo
    ├── categorizer.py         ← Extension/MIME classification + plugin system
    ├── duplicate_handler.py   ← Conflict resolution strategies
    └── mover.py               ← File/folder I/O, preview mode, move history


tests/
    └── test_organizer.py      ← Unit + integration tests (pytest)
```

### Data flow

```text
main.py / gui.py / your code
       │
       ▼
 FileOrganizer.run()                ← core.py (façade)
       │
       ├─ DirectoryScanner.scan()    ← scanner.py
       │      ├─ yields FileInfo
       │      └─ yields DashFolderInfo for excluded dash-folders
       │
       ├─ Categorizer.categorize()   ← categorizer.py
       │      └─ extension map → MIME fallback → custom plugins
       │
       ├─ DuplicateHandler.resolve() ← duplicate_handler.py
       │
       └─ FileMover.move()           ← mover.py
              ├─ move_file()
              └─ move_folder()
```

### How dash-folders flow through the pipeline

Folders whose names begin with `-` are treated as protected/excluded folders when dash-folder exclusion is enabled.

* They are not recursively scanned
* Their contents are not categorized individually
* The folder is moved intact as a whole
* The move destination uses the configured excluded-folder target

This keeps private or special-purpose folders together while still organizing the rest of the directory normally.

---

## 📁 Folder Organization Logic

Files are sorted into category and subcategory folders based on extension or MIME type.

Example input:

```text
DIR/
├── random.pdf
├── image1.png
├── notes.docx
├── -Personal/
│   ├── private.docx
│   └── notes.txt
```

Example output:

```text
Organized/
├── Documents/
│   ├── PDF/
│   │   └── random.pdf
│   └── DOCX/
│       └── notes.docx
├── Photos/
│   └── PNG/
│       └── image1.png
└── Excluded/
    └── -Personal/
        ├── private.docx
        └── notes.txt
```

---

## 🚫 Excluded Dash Folders

One of the biggest problems with automatic organizers is that they can accidentally tear apart folders you intentionally grouped together.

This project solves that problem using protected dash-folders.

Folders beginning with `-` are treated as protected folders when dash-folder exclusion is enabled.

### Examples

* `-Personal`
* `-Archive`
* `-Old Files`

### Behavior

* excluded from recursive scanning
* contents remain untouched during organization
* moved as intact folders instead of being broken apart
* configurable in GUI, CLI, and `config.json`

### Why this exists

This makes it easy to keep special folders together while still allowing the organizer to sort the rest of the directory.

### Safety benefit

A dash-folder is treated as a folder-level unit, which reduces the chance of accidentally scattering files that were meant to stay grouped together.

---

## ⚙️ Configuration

Edit `config.json` to add or remap file types:

```json
{
  "categories": {
    "Documents": {
      "subcategories": {
        "PDF": ["pdf"],
        "DOCX": ["docx", "doc"],
        "TXT": ["txt", "md"]
      }
    },
    "Photos": {
      "subcategories": {
        "PNG": ["png"],
        "JPG": ["jpg", "jpeg"]
      }
    }
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

### Setting reference

* `duplicate_strategy` — how filename collisions are handled
* `recursive` — whether subfolders are scanned
* `preview_mode` — show planned actions without moving files
* `skip_hidden_files` — ignore hidden files when scanning
* `exclude_dash_folders` — treat `-FolderName` folders as excluded and move them intact
* `excluded_folder_name` — destination folder used for excluded dash-folders
* `uncategorized_folder` — destination for files that do not match any rule

YAML format is also supported — just name your file `config.yaml`.

---

## 🔌 Adding AI / Custom Plugins

The categorizer has a plugin system. Implement `CategoryPlugin` to add custom logic — AI models, content inspection, OCR, or metadata-based rules.

```python
from organizer.categorizer import CategoryPlugin
from organizer.scanner import FileInfo


class MyAIPlugin(CategoryPlugin):
    name = "my_ai_classifier"

    def categorize(self, file_info: FileInfo):
        if self._is_receipt(file_info):
            return ("Finance", "Receipts")
        return None

    def _is_receipt(self, fi: FileInfo) -> bool:
        ...


from organizer import FileOrganizer

organizer = FileOrganizer(source_dir="~/Downloads")
organizer.register_plugin(MyAIPlugin())
organizer.run()
```

Plugins are tried after extension and MIME lookups fail, so they add minimal overhead for already-known file types.

---

## 🧪 Running Tests

```bash
# All tests
python -m pytest tests/ -v

# With coverage report
python -m pytest tests/ --cov=organizer --cov-report=term-missing

# Single test class
python -m pytest tests/test_organizer.py::TestEndToEnd -v
```

---

## 🛠️ Automatic Dependency Installation

No more confusing `ModuleNotFoundError` crashes during first launch.

The project includes a lightweight bootstrap system that automatically detects missing packages, installs dependencies from `requirements.txt`, and relaunches the application safely.

The project includes a bootstrap pattern for missing dependency handling.

### What it does

* detects `ModuleNotFoundError`
* attempts to install dependencies from `requirements.txt`
* retries execution after installation
* avoids infinite install loops
* shows clear logs if installation fails

### Notes

* This is meant as a convenience layer for first-run setup
* In production or controlled environments, pre-install dependencies manually when possible
* Keep `requirements.txt` reviewed and pinned as needed for stability

---

## 🖥️ GUI Recommendations

| Option                | Pros                           | Cons                               | Verdict       |
| --------------------- | ------------------------------ | ---------------------------------- | ------------- |
| **Tkinter**           | Built-in, no install           | Basic look                         | Skip          |
| **CustomTkinter**     | Modern look, easy, pure Python | Less flexible than full frameworks | ✅ Best for v1 |
| **PyQt6**             | Very powerful, native feel     | Steeper learning curve             | Good for v2   |
| **Electron + Python** | Web-tech UI                    | Heavy and complex                  | Overkill      |

CustomTkinter gives the project a modern desktop look with a manageable codebase and good cross-platform support.

---

## 🛣️ Development Roadmap

### Phase 1 — Core

* [x] Extension + MIME categorization
* [x] Duplicate handling (3 strategies)
* [x] Preview mode
* [x] Recursive scanning
* [x] Dash-folder exclusion support
* [x] Configurable via JSON/YAML
* [x] Plugin architecture
* [x] Core test suite

### Phase 2 — Real-time Monitoring

* [ ] `watchdog`-based folder watcher
* [ ] Background daemon / system service
* [ ] Windows Task Scheduler / macOS launchd integration

### Phase 3 — Database & History

* [ ] SQLite schema for file history
* [ ] Track original locations → enable undo
* [ ] File metadata indexing
* [ ] Full-text search

### Phase 4 — AI Features

* [ ] Document content analysis (receipts, invoices, contracts)
* [ ] OCR for scanned image files (`pytesseract`)
* [ ] LLM-based semantic tagging
* [ ] Smart folder suggestions based on usage patterns

### Phase 5 — GUI

* [ ] CustomTkinter desktop UI
* [ ] Sidebar navigation
* [ ] Drag-and-drop source folder selection
* [ ] Progress bar and log view
* [ ] Move history table with undo support

---

## 🔒 Security Considerations

* The organizer does not delete files; it moves them.
* Always run with `--preview` first on important directories.
* Use `--output` to keep source and destination separate for extra safety.
* Dash-folders are handled as intact folder units when exclusion is enabled.
* Automatic dependency installation is a convenience feature and should be used with care.
* No network connections are made by the core organizer modules.

---

## 📜 License

MIT — free to use, modify, and distribute.
