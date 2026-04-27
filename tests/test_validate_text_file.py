"""Unit tests for epub2tts_chatterbox.text_utils.validate_text_file."""
import logging
from pathlib import Path

import pytest

from epub2tts_chatterbox.text_utils import validate_text_file


def _write(tmp_path: Path, content: str) -> str:
    p = tmp_path / "book.txt"
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestValidateTextFile:
    def test_valid_file_does_not_exit(self, tmp_path: Path):
        path = _write(tmp_path, "# A Chapter\nSome paragraph text.\n")
        # All required pieces present (title, author, chapter break) — should not raise.
        validate_text_file(path, "My Book", "Jane Doe", [{"title": "A Chapter", "paragraphs": ["Some paragraph text."]}])

    def test_missing_title_exits_with_code_1(self, tmp_path: Path):
        path = _write(tmp_path, "# A Chapter\nBody.\n")
        with pytest.raises(SystemExit) as exc_info:
            # When Title is missing, get_book leaves book_title == sourcefile path
            validate_text_file(path, path, "Some Author", [])
        assert exc_info.value.code == 1

    def test_missing_author_exits(self, tmp_path: Path):
        path = _write(tmp_path, "# A Chapter\nBody.\n")
        with pytest.raises(SystemExit):
            validate_text_file(path, "Some Title", "Unknown", [])

    def test_missing_chapter_break_exits(self, tmp_path: Path):
        # File has neither a leading '#' line.
        path = _write(tmp_path, "Just plain text with no chapter markers.\n")
        with pytest.raises(SystemExit):
            validate_text_file(path, "Some Title", "Some Author", [])

    def test_all_three_missing_logs_all_errors(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ):
        path = _write(tmp_path, "Just text. No title, no author, no chapter break.\n")
        with caplog.at_level(logging.ERROR, logger="epub2tts_chatterbox.text_utils"):
            with pytest.raises(SystemExit):
                validate_text_file(path, path, "Unknown", [])

        full_log = caplog.text
        assert "Title" in full_log
        assert "Author" in full_log
        assert "chapter break" in full_log

    def test_chapter_break_anywhere_in_file_passes(self, tmp_path: Path):
        # The chapter-break check scans the whole file, so even a late '#' line counts.
        path = _write(
            tmp_path,
            "Some intro text on line one.\n"
            "Another line without a marker.\n"
            "# Late Chapter Marker\n"
            "Body text.\n",
        )
        # All other fields valid; chapter break exists deep in the file → no exit.
        validate_text_file(path, "Title", "Author", [])
