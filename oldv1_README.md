# 🗂️ Intelligent File Organizer

A modular, production-ready Python tool that automatically sorts messy
directories into clean, categorized folder structures — with an architecture
designed to grow into an AI-powered personal file management system.

---

## ✨ Features

| Feature | Status |
|---|---|
| Extension-based categorization | ✅ |
| MIME-type fallback | ✅ |
| Duplicate handling (counter / timestamp / skip) | ✅ |
| Preview / dry-run mode | ✅ |
| Recursive directory scanning | ✅ |
| JSON & YAML config files | ✅ |
| Structured logging (console + rotating file) | ✅ |
| Custom categorization plugins | ✅ |
| AI classification hook | 🔜 plug-in ready |
| Real-time folder monitoring (watchdog) | 🔜 |
| SQLite file history database | 🔜 |
| GUI (CustomTkinter) | 🔜 |

---

## 🚀 Quick Start

```bash
# 1. Clone / download the project
cd intelligent_file_organizer

# 2. (Optional) Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Preview what will happen — no files moved
python main.py /path/to/your/downloads --preview

# 5. Run for real
python main.py /path/to/your/downloads

# 6. Organise into a separate output folder
python main.py ~/Downloads --output ~/Organized
```

---

## 📖 CLI Reference

```
python main.py SOURCE_DIR [OPTIONS]

Options:
  --output,    -o DIR    Output directory (defaults to SOURCE_DIR)
  --config,    -c FILE   Custom JSON or YAML config file
  --preview,   -p        Dry-run: show planned moves without executing
  --recursive, -r        Scan subdirectories recursively
  --duplicate-strategy   counter | timestamp | skip  (default: counter)
  --no-log-file          Console-only logging
  --log-file   FILE      Custom log file path
  --verbose,   -v        Enable DEBUG output
```

---

## 🏗️ Project Architecture

```
intelligent_file_organizer/
│
├── main.py                    ← CLI entry point (argparse)
├── config.json                ← Default extension mappings & settings
├── requirements.txt
│
└── organizer/                 ← Core library (importable as a package)
    ├── __init__.py            ← Exports FileOrganizer
    ├── core.py                ← Façade orchestrator — wires everything together
    ├── config_manager.py      ← JSON/YAML config loading → OrganizerConfig
    ├── logger.py              ← Shared logger (console + rotating file)
    ├── scanner.py             ← Directory traversal → FileInfo stream
    ├── categorizer.py         ← Extension/MIME classification + plugin system
    ├── duplicate_handler.py   ← Conflict resolution strategies
    └── mover.py               ← File I/O, preview mode, move history

tests/
    └── test_organizer.py      ← 25+ unit & integration tests (pytest)
```

### Data flow

```
main.py / your code
       │
       ▼
 FileOrganizer.run()                ← core.py (façade)
       │
       ├─ DirectoryScanner.scan()   ← scanner.py   → yields FileInfo
       │
       ├─ Categorizer.categorize()  ← categorizer.py → sets .category / .subcategory
       │       └─ Plugin chain: extension map → MIME fallback → custom plugins
       │
       └─ FileMover.move()          ← mover.py
               └─ duplicate_handler.resolve()
```

---

## ⚙️ Configuration

Edit `config.json` to add or remap file types:

```json
{
  "categories": {
    "Documents": {
      "subcategories": {
        "PDF":  ["pdf"],
        "DOCX": ["docx", "doc"],
        "TXT":  ["txt", "md"]
      }
    },
    "MyCustomCategory": {
      "subcategories": {
        "Drawings": ["dwg", "dxf"],
        "Other":    []
      }
    }
  },
  "settings": {
    "duplicate_strategy": "counter",
    "recursive": false,
    "preview_mode": false,
    "skip_hidden_files": true,
    "uncategorized_folder": "Uncategorized"
  }
}
```

YAML format is also supported — just name your file `config.yaml`.

---

## 🔌 Adding AI / Custom Plugins

The categorizer has a plugin system. Implement `CategoryPlugin` to add any
custom logic — AI models, content inspection, OCR, etc.

```python
from organizer.categorizer import CategoryPlugin
from organizer.scanner import FileInfo

class MyAIPlugin(CategoryPlugin):
    name = "my_ai_classifier"

    def categorize(self, file_info: FileInfo):
        # Call your AI model, do OCR, read file headers, etc.
        # Return (category, subcategory) or None to pass to next plugin
        if self._is_receipt(file_info):
            return ("Finance", "Receipts")
        return None

    def _is_receipt(self, fi: FileInfo) -> bool:
        # Your logic here
        ...

# Register it
from organizer import FileOrganizer
organizer = FileOrganizer(source_dir="~/Downloads")
organizer.register_plugin(MyAIPlugin())
organizer.run()
```

Plugins are tried **only after** the extension/MIME lookups fail, so they
add zero latency for already-known file types.

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

## 🛣️ Development Roadmap

### Phase 1 — Core (complete)
- [x] Extension + MIME categorization
- [x] Duplicate handling (3 strategies)
- [x] Preview mode
- [x] Recursive scanning
- [x] Configurable via JSON/YAML
- [x] Plugin architecture
- [x] Full test suite

### Phase 2 — Real-time Monitoring
- [ ] `watchdog`-based folder watcher
- [ ] Background daemon / system service
- [ ] Windows Task Scheduler / macOS launchd integration

### Phase 3 — Database & History
- [ ] SQLite schema for file history
- [ ] Track original locations → enable undo
- [ ] File metadata indexing
- [ ] Full-text search

### Phase 4 — AI Features
- [ ] Document content analysis (detect receipts, invoices, contracts)
- [ ] OCR for scanned image files (pytesseract)
- [ ] LLM-based semantic tagging (Claude / OpenAI)
- [ ] Smart folder suggestions based on usage patterns

### Phase 5 — GUI
- [ ] CustomTkinter desktop UI (recommended for simplicity)
- [ ] Drag-and-drop source folder selection
- [ ] Real-time progress bar
- [ ] Move history table with undo support

---

## 🖥️ GUI Recommendations

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Tkinter** | Built-in, no install | Ugly by default | Skip |
| **CustomTkinter** | Modern look, easy, pure Python | Less flexible | ✅ **Best for v1** |
| **PyQt6** | Very powerful, native look | Steep learning curve | Good for v2 |
| **Electron + Python** | Web tech UI | Heavy (100 MB+), complex IPC | Overkill |

CustomTkinter gives you a modern, cross-platform desktop app in ~200 lines
of Python with no UI framework knowledge required.

---

## 🔒 Security Considerations

- The organizer **never deletes** files — it only moves them.
- Always run with `--preview` first on important directories.
- The output directory defaults to the source directory — use `--output` to
  keep source and destination separate for extra safety.
- File permissions are preserved by `shutil.move`.
- No network connections are made by any core module.

---

## 📜 License

MIT — free to use, modify, and distribute.
