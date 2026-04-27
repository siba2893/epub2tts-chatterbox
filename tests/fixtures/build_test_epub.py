"""Build a tiny 1-chapter EPUB fixture for end-to-end smoke testing.

Run from the repo root:
    python tests/fixtures/build_test_epub.py

Produces ``tests/fixtures/sample.epub``. Use it to exercise the EPUB-export
branch of the CLI:
    epub2tts-chatterbox tests/fixtures/sample.epub
"""
import os
from pathlib import Path

from ebooklib import epub


def build(out_path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("smoke-test-book-001")
    book.set_title("Smoke Test Book")
    book.set_language("en")
    book.add_author("Test Author")

    chapter1 = epub.EpubHtml(title="The First Chapter", file_name="chap_01.xhtml", lang="en")
    chapter1.content = (
        "<h1>The First Chapter</h1>"
        "<p>The morning light spilled across the wooden floor in long golden ribbons, "
        "slow and patient and warm. Somewhere outside, a single bird was rehearsing "
        "the same three notes over and over.</p>"
        "<p>She set down her cup, listened for a moment, and then opened the book to "
        "the first page.</p>"
    )

    chapter2 = epub.EpubHtml(title="A Brief Second Chapter", file_name="chap_02.xhtml", lang="en")
    chapter2.content = (
        "<h1>A Brief Second Chapter</h1>"
        "<p>There was nothing else to say. The story had already begun without her.</p>"
    )

    book.add_item(chapter1)
    book.add_item(chapter2)

    book.toc = (chapter1, chapter2)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter1, chapter2]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(out_path), book)
    print(f"Wrote {out_path} ({os.path.getsize(out_path)} bytes)")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    build(here / "sample.epub")
