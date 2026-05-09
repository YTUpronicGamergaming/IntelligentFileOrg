"""
tests/test_organizer.py
-----------------------
Comprehensive unit tests covering all core modules.

Run with:
    python -m pytest tests/ -v

Or a single module:
    python -m pytest tests/test_organizer.py::TestCategorizer -v
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_dir():
    """Create and clean up a temporary directory for each test."""
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def config():
    """Load the default config bundled with the project."""
    from organizer.config_manager import load_config
    return load_config()


def make_file(directory: Path, name: str, content: str = "test") -> Path:
    """Helper: create a file in directory with given content."""
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# ConfigManager tests
# ---------------------------------------------------------------------------

class TestConfigManager:

    def test_load_default_config(self, config):
        assert config.categories, "Categories should not be empty"
        assert "Documents" in config.categories
        assert "Photos" in config.categories

    def test_extension_map_built(self, config):
        assert "pdf" in config.extension_map
        assert "png" in config.extension_map
        assert config.extension_map["pdf"] == ("Documents", "PDF")

    def test_resolve_known_extension(self, config):
        cat, sub = config.resolve("pdf")
        assert cat == "Documents"
        assert sub == "PDF"

    def test_resolve_unknown_extension_returns_uncategorized(self, config):
        cat, sub = config.resolve("xyz_unknown_ext")
        assert cat == config.settings.uncategorized_folder

    def test_missing_config_raises(self):
        from organizer.config_manager import ConfigManager
        with pytest.raises(FileNotFoundError):
            ConfigManager("/nonexistent/path/config.json").load()

    def test_invalid_config_format_raises(self, temp_dir):
        from organizer.config_manager import ConfigManager
        bad = temp_dir / "config.toml"
        bad.write_text("[settings]", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported config format"):
            ConfigManager(bad).load()


# ---------------------------------------------------------------------------
# Scanner tests
# ---------------------------------------------------------------------------

class TestDirectoryScanner:

    def test_finds_files(self, temp_dir):
        make_file(temp_dir, "a.txt")
        make_file(temp_dir, "b.pdf")
        from organizer.scanner import DirectoryScanner
        scanner = DirectoryScanner(temp_dir)
        files = list(scanner.scan())
        assert len(files) == 2

    def test_skips_hidden_files(self, temp_dir):
        make_file(temp_dir, "visible.txt")
        make_file(temp_dir, ".hidden")
        from organizer.scanner import DirectoryScanner
        scanner = DirectoryScanner(temp_dir, skip_hidden=True)
        names = [f.name for f in scanner.scan()]
        assert "visible.txt" in names
        assert ".hidden" not in names

    def test_skips_system_files(self, temp_dir):
        make_file(temp_dir, "Thumbs.db")
        make_file(temp_dir, "real.jpg")
        from organizer.scanner import DirectoryScanner
        scanner = DirectoryScanner(temp_dir, system_patterns=["Thumbs.db"])
        names = [f.name for f in scanner.scan()]
        assert "real.jpg" in names
        assert "Thumbs.db" not in names

    def test_recursive_scan(self, temp_dir):
        sub = temp_dir / "subdir"
        sub.mkdir()
        make_file(temp_dir, "root.txt")
        make_file(sub, "nested.txt")
        from organizer.scanner import DirectoryScanner
        scanner = DirectoryScanner(temp_dir, recursive=True)
        names = [f.name for f in scanner.scan()]
        assert "root.txt" in names
        assert "nested.txt" in names

    def test_non_recursive_excludes_nested(self, temp_dir):
        sub = temp_dir / "subdir"
        sub.mkdir()
        make_file(temp_dir, "root.txt")
        make_file(sub, "nested.txt")
        from organizer.scanner import DirectoryScanner
        scanner = DirectoryScanner(temp_dir, recursive=False)
        names = [f.name for f in scanner.scan()]
        assert "root.txt" in names
        assert "nested.txt" not in names

    def test_raises_on_missing_directory(self):
        from organizer.scanner import DirectoryScanner
        with pytest.raises(FileNotFoundError):
            list(DirectoryScanner(Path("/no/such/dir")).scan())

    def test_fileinfo_properties(self, temp_dir):
        p = make_file(temp_dir, "report.pdf", "hello")
        from organizer.scanner import DirectoryScanner
        files = list(DirectoryScanner(temp_dir).scan())
        assert len(files) == 1
        fi = files[0]
        assert fi.extension == "pdf"
        assert fi.name == "report.pdf"
        assert fi.stem == "report"
        assert fi.size_bytes == len("hello")

    def test_min_size_filter(self, temp_dir):
        make_file(temp_dir, "small.txt", "x")          # 1 byte
        make_file(temp_dir, "large.txt", "x" * 1000)   # 1000 bytes
        from organizer.scanner import DirectoryScanner
        scanner = DirectoryScanner(temp_dir, min_size_bytes=100)
        names = [f.name for f in scanner.scan()]
        assert "large.txt" in names
        assert "small.txt" not in names


# ---------------------------------------------------------------------------
# Categorizer tests
# ---------------------------------------------------------------------------

class TestCategorizer:

    def test_categorizes_pdf(self, temp_dir, config):
        from organizer.scanner import FileInfo
        from organizer.categorizer import Categorizer
        make_file(temp_dir, "doc.pdf")
        fi = FileInfo.from_path(temp_dir / "doc.pdf", temp_dir)
        cat = Categorizer(config)
        result = cat.categorize(fi)
        assert result.category == "Documents"
        assert result.subcategory == "PDF"

    def test_categorizes_png(self, temp_dir, config):
        from organizer.scanner import FileInfo
        from organizer.categorizer import Categorizer
        make_file(temp_dir, "img.png")
        fi = FileInfo.from_path(temp_dir / "img.png", temp_dir)
        result = Categorizer(config).categorize(fi)
        assert result.category == "Photos"
        assert result.subcategory == "PNG"

    def test_categorizes_mp3(self, temp_dir, config):
        from organizer.scanner import FileInfo
        from organizer.categorizer import Categorizer
        make_file(temp_dir, "song.mp3")
        fi = FileInfo.from_path(temp_dir / "song.mp3", temp_dir)
        result = Categorizer(config).categorize(fi)
        assert result.category == "Audio"

    def test_unknown_extension_goes_to_uncategorized(self, temp_dir, config):
        from organizer.scanner import FileInfo
        from organizer.categorizer import Categorizer
        make_file(temp_dir, "file.xyzabc123")
        fi = FileInfo.from_path(temp_dir / "file.xyzabc123", temp_dir)
        result = Categorizer(config).categorize(fi)
        assert result.category == config.settings.uncategorized_folder

    def test_custom_plugin_is_called(self, temp_dir, config):
        from organizer.scanner import FileInfo
        from organizer.categorizer import Categorizer, CategoryPlugin
        make_file(temp_dir, "file.xyzabc123")
        fi = FileInfo.from_path(temp_dir / "file.xyzabc123", temp_dir)

        class AlwaysDocuments(CategoryPlugin):
            name = "always_documents"
            def categorize(self, f):
                return ("Documents", "Other")

        cat = Categorizer(config)
        cat.register_plugin(AlwaysDocuments())
        result = cat.categorize(fi)
        assert result.category == "Documents"


# ---------------------------------------------------------------------------
# Duplicate handler tests
# ---------------------------------------------------------------------------

class TestDuplicateHandler:

    def test_no_conflict_returns_original(self, temp_dir):
        from organizer.duplicate_handler import resolve
        dest = temp_dir / "newfile.txt"
        assert resolve(dest) == dest

    def test_counter_strategy(self, temp_dir):
        from organizer.duplicate_handler import resolve
        original = temp_dir / "photo.png"
        make_file(temp_dir, "photo.png")  # Create the conflict
        resolved = resolve(original, strategy="counter")
        assert resolved is not None
        assert resolved.name == "photo (1).png"

    def test_counter_increments(self, temp_dir):
        from organizer.duplicate_handler import resolve
        make_file(temp_dir, "photo.png")
        make_file(temp_dir, "photo (1).png")
        original = temp_dir / "photo.png"
        resolved = resolve(original, strategy="counter")
        assert resolved is not None
        assert resolved.name == "photo (2).png"

    def test_timestamp_strategy_produces_unique_name(self, temp_dir):
        from organizer.duplicate_handler import resolve
        make_file(temp_dir, "photo.png")
        original = temp_dir / "photo.png"
        resolved = resolve(original, strategy="timestamp")
        assert resolved is not None
        assert resolved.name != "photo.png"
        assert "photo_" in resolved.name

    def test_skip_strategy_returns_none(self, temp_dir):
        from organizer.duplicate_handler import resolve
        make_file(temp_dir, "photo.png")
        original = temp_dir / "photo.png"
        assert resolve(original, strategy="skip") is None

    def test_invalid_strategy_raises(self, temp_dir):
        from organizer.duplicate_handler import resolve
        make_file(temp_dir, "photo.png")
        with pytest.raises(ValueError, match="Unknown duplicate strategy"):
            resolve(temp_dir / "photo.png", strategy="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# FileMover tests
# ---------------------------------------------------------------------------

class TestFileMover:

    def _make_file_info(self, directory: Path, name: str, category: str, subcategory: str):
        from organizer.scanner import FileInfo
        make_file(directory, name)
        fi = FileInfo.from_path(directory / name, directory)
        fi.category = category
        fi.subcategory = subcategory
        return fi

    def test_preview_mode_does_not_move(self, temp_dir):
        from organizer.mover import FileMover, MoveStatus
        fi = self._make_file_info(temp_dir, "doc.pdf", "Documents", "PDF")
        output = temp_dir / "output"
        mover = FileMover(output_root=output, preview_mode=True)
        result = mover.move(fi)
        assert result.status == MoveStatus.PREVIEW
        assert not (output / "Documents" / "PDF" / "doc.pdf").exists()
        assert (temp_dir / "doc.pdf").exists()  # Still in source

    def test_live_move_creates_file(self, temp_dir):
        from organizer.mover import FileMover, MoveStatus
        fi = self._make_file_info(temp_dir, "song.mp3", "Audio", "MP3")
        output = temp_dir / "output"
        mover = FileMover(output_root=output, preview_mode=False)
        result = mover.move(fi)
        assert result.status == MoveStatus.MOVED
        assert (output / "Audio" / "MP3" / "song.mp3").exists()

    def test_destination_directories_created(self, temp_dir):
        from organizer.mover import FileMover
        fi = self._make_file_info(temp_dir, "img.png", "Photos", "PNG")
        output = temp_dir / "deep" / "nested" / "output"
        mover = FileMover(output_root=output)
        mover.move(fi)
        assert (output / "Photos" / "PNG" / "img.png").exists()

    def test_duplicate_counter_on_conflict(self, temp_dir):
        from organizer.mover import FileMover, MoveStatus
        output = temp_dir / "output"
        # Pre-create the conflict
        dest_dir = output / "Documents" / "PDF"
        dest_dir.mkdir(parents=True)
        (dest_dir / "report.pdf").write_text("existing", encoding="utf-8")

        fi = self._make_file_info(temp_dir, "report.pdf", "Documents", "PDF")
        mover = FileMover(output_root=output, duplicate_strategy="counter")
        result = mover.move(fi)
        assert result.status == MoveStatus.MOVED
        assert (dest_dir / "report (1).pdf").exists()

    def test_stats_are_accumulated(self, temp_dir):
        from organizer.mover import FileMover
        output = temp_dir / "output"
        fi1 = self._make_file_info(temp_dir, "a.pdf", "Documents", "PDF")
        fi2 = self._make_file_info(temp_dir, "b.png", "Photos", "PNG")
        mover = FileMover(output_root=output)
        mover.move(fi1)
        mover.move(fi2)
        assert mover.stats["moved"] == 2
        assert mover.stats["total"] == 2


# ---------------------------------------------------------------------------
# End-to-end integration test
# ---------------------------------------------------------------------------

class TestEndToEnd:

    def test_full_run_preview(self, temp_dir):
        """Preview run should categorize all files without moving any."""
        make_file(temp_dir, "report.pdf")
        make_file(temp_dir, "image.jpg")
        make_file(temp_dir, "song.mp3")
        make_file(temp_dir, "archive.zip")
        make_file(temp_dir, "mystery.xyzabc")

        from organizer import FileOrganizer
        organizer = FileOrganizer(
            source_dir=temp_dir,
            preview_mode=True,
            log_to_file=False,
        )
        result = organizer.run()

        assert result.total == 5
        assert result.previewed == 5
        assert result.moved == 0
        assert result.errors == 0

        # Source files must still be in place
        assert (temp_dir / "report.pdf").exists()
        assert (temp_dir / "image.jpg").exists()

    def test_full_run_live(self, temp_dir):
        """Live run should move all files to correct destinations."""
        make_file(temp_dir, "report.pdf")
        make_file(temp_dir, "photo.png")
        make_file(temp_dir, "music.mp3")

        output = temp_dir / "organized"

        from organizer import FileOrganizer
        organizer = FileOrganizer(
            source_dir=temp_dir,
            output_dir=output,
            preview_mode=False,
            log_to_file=False,
        )
        result = organizer.run()

        assert result.moved == 3
        assert result.errors == 0
        assert (output / "Documents" / "PDF" / "report.pdf").exists()
        assert (output / "Photos" / "PNG" / "photo.png").exists()
        assert (output / "Audio" / "MP3" / "music.mp3").exists()
