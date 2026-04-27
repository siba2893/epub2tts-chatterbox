"""Unit tests for epub2tts_chatterbox.text_utils.get_book."""
from pathlib import Path

import pytest

from epub2tts_chatterbox.text_utils import get_book


def _write(tmp_path: Path, content: str) -> str:
    p = tmp_path / "book.txt"
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestGetBook:
    def test_minimal_valid_file(self, tmp_path: Path):
        path = _write(
            tmp_path,
            "Title: My Book\n"
            "Author: Jane Doe\n"
            "\n"
            "# Chapter One\n"
            "\n"
            "This is the first paragraph of chapter one.\n"
            "It has only one paragraph.\n",
        )
        contents, title, author, chapter_titles = get_book(path)

        assert title == "My Book"
        assert author == "Jane Doe"
        assert chapter_titles == ["Chapter One"]
        assert len(contents) == 1
        assert contents[0]["title"] == "Chapter One"
        # Each non-blank line becomes its own paragraph entry
        assert len(contents[0]["paragraphs"]) == 2

    def test_multiple_chapters_split_correctly(self, tmp_path: Path):
        path = _write(
            tmp_path,
            "Title: Two-Chapter Book\n"
            "Author: Test\n"
            "\n"
            "# First\n"
            "Hello world from chapter one.\n"
            "\n"
            "# Second\n"
            "And here we are in chapter two.\n",
        )
        contents, _, _, chapter_titles = get_book(path)

        assert chapter_titles == ["First", "Second"]
        assert len(contents) == 2
        assert contents[0]["title"] == "First"
        assert contents[1]["title"] == "Second"
        assert "chapter one" in contents[0]["paragraphs"][0]
        assert "chapter two" in contents[1]["paragraphs"][0]

    def test_missing_title_returns_sourcefile_path(self, tmp_path: Path):
        # No "Title: ..." line at all — book_title should fall back to sourcefile path,
        # which is what validate_text_file looks for.
        path = _write(
            tmp_path,
            "Author: Anonymous\n"
            "\n"
            "# Only Chapter\n"
            "Some text.\n",
        )
        _, title, _, _ = get_book(path)
        assert title == path

    def test_missing_author_defaults_to_unknown(self, tmp_path: Path):
        path = _write(
            tmp_path,
            "Title: A Book\n"
            "\n"
            "# A Chapter\n"
            "Some text here.\n",
        )
        _, _, author, _ = get_book(path)
        assert author == "Unknown"

    def test_chapter_with_non_alphanumeric_title_becomes_blank(self, tmp_path: Path):
        path = _write(
            tmp_path,
            "Title: Edge Case\n"
            "Author: Test\n"
            "\n"
            "# ***\n"
            "Body text.\n",
        )
        _, _, _, chapter_titles = get_book(path)
        assert chapter_titles == ["blank"]

    def test_pre_chapter_text_creates_blank_first_chapter(self, tmp_path: Path):
        # Text appearing before any "#" line should land in a chapter whose
        # title slot is recorded as "blank" in chapter_titles.
        path = _write(
            tmp_path,
            "Title: Pre-Chapter Book\n"
            "Author: Test\n"
            "\n"
            "Some prologue text before any chapter break.\n"
            "\n"
            "# Chapter One\n"
            "Real chapter content.\n",
        )
        contents, _, _, chapter_titles = get_book(path)

        # chapter_titles starts with "blank" (for the pre-chapter text), then "Chapter One"
        assert chapter_titles[0] == "blank"
        assert "Chapter One" in chapter_titles
        assert len(contents) >= 1

    def test_lines_without_alphanumerics_are_skipped(self, tmp_path: Path):
        path = _write(
            tmp_path,
            "Title: Filter Test\n"
            "Author: Test\n"
            "\n"
            "# The Chapter\n"
            "\n"
            "Real paragraph one.\n"
            "***\n"
            "Real paragraph two.\n",
        )
        contents, _, _, _ = get_book(path)
        for paragraph in contents[0]["paragraphs"]:
            assert any(ch.isalnum() for ch in paragraph)

    def test_existing_sample_fixture(self):
        """Smoke-test against the committed sample.txt fixture."""
        fixture = Path(__file__).parent / "fixtures" / "sample.txt"
        contents, title, author, chapter_titles = get_book(str(fixture))

        assert title == "Smoke Test Book"
        assert author == "Test Author"
        assert chapter_titles == ["The First Chapter", "A Brief Second Chapter"]
        assert len(contents) == 2
