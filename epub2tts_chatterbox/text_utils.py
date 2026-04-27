"""Pure text/formatting utilities used by the TTS pipeline.

Kept free of heavy imports (torch, chatterbox) so they can be unit-tested
without a GPU or model download.
"""
from __future__ import annotations

import logging
import re
import sys
from typing import Any

from nltk.tokenize import sent_tokenize

logger = logging.getLogger(__name__)


def conditional_sentence_case(sent: str) -> str:
    """Lowercase + capitalize a sentence if it has 3+ consecutive UPPERCASE words.

    Heuristic for headings/shouted text that would otherwise be read aloud
    letter-by-letter by the TTS model.
    """
    words = sent.split()
    length = len(words)
    for i in range(length - 2):
        if words[i].isupper() and words[i + 1].isupper() and words[i + 2].isupper():
            sent = " ".join(words).lower().capitalize()
            break
    return sent


def format_time_adaptive(seconds: float) -> str:
    """Format seconds as the largest two relevant units (s / m s / h m)."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def sort_key(s: str) -> int:
    """Sort key that extracts the first integer in a filename like 'sntnc12.wav'."""
    return int(re.findall(r"\d+", s)[0])


def combine_short_paragraphs(paragraphs: list[str], min_words: int = 6) -> list[str]:
    """Merge a single-sentence paragraph shorter than ``min_words`` into the next one."""
    if not paragraphs:
        return []

    result: list[str] = []
    i = 0
    while i < len(paragraphs):
        paragraph = paragraphs[i]
        sentences = sent_tokenize(paragraph)
        if len(sentences) == 1 and len(paragraph.split()) < min_words:
            if i + 1 < len(paragraphs):
                result.append(paragraph + " " + paragraphs[i + 1])
                i += 2
            else:
                result.append(paragraph)
                i += 1
        else:
            result.append(paragraph)
            i += 1
    return result


def combine_short_sentences(
    sentences: list[str], min_words: int = 6, keep_threshold: int = 8
) -> list[str]:
    """Combine short sentences within a paragraph.

    Sentences with >= ``keep_threshold`` words pass through unchanged; shorter
    runs are merged until they reach ``min_words``. Trailing remainder is
    appended to the previous chunk if it is itself shorter than ``min_words``.
    """
    if not sentences:
        return []

    result: list[str] = []
    current_chunk = ""
    for i, sentence in enumerate(sentences):
        word_count = len(sentence.split())

        if not current_chunk:
            current_chunk = sentence
            if word_count >= keep_threshold and i < len(sentences) - 1:
                result.append(current_chunk)
                current_chunk = ""
        else:
            current_chunk += " " + sentence

        chunk_words = len(current_chunk.split())
        if chunk_words >= keep_threshold or (
            chunk_words >= min_words and i < len(sentences) - 1
        ):
            result.append(current_chunk)
            current_chunk = ""

    if current_chunk:
        if result and len(current_chunk.split()) < min_words:
            result[-1] += " " + current_chunk
        else:
            result.append(current_chunk)
    return result


def get_book(sourcefile: str) -> tuple[list[dict[str, Any]], str, str, list[str]]:
    """Parse a stage-2 ``.txt`` file into chapters, title, author, and chapter titles.

    The text file must contain ``Title:`` and ``Author:`` headers and chapter
    breaks marked with leading ``#``. Lines without alphanumerics are skipped.
    """
    book_contents: list[dict[str, Any]] = []
    book_title = sourcefile
    book_author = "Unknown"
    chapter_titles: list[str] = []

    with open(sourcefile, "r", encoding="utf-8") as file:
        current_chapter: dict[str, Any] = {"title": "blank", "paragraphs": []}
        initialized_first_chapter = False
        lines_skipped = 0
        for line in file:
            if lines_skipped < 2 and (line.startswith("Title") or line.startswith("Author")):
                lines_skipped += 1
                if line.startswith("Title: "):
                    book_title = line.replace("Title: ", "").strip()
                elif line.startswith("Author: "):
                    book_author = line.replace("Author: ", "").strip()
                continue

            line = line.strip()
            if line.startswith("#"):
                if current_chapter["paragraphs"] or not initialized_first_chapter:
                    if initialized_first_chapter:
                        book_contents.append(current_chapter)
                    current_chapter = {"title": None, "paragraphs": []}
                    initialized_first_chapter = True
                chapter_title = line[1:].strip()
                if any(c.isalnum() for c in chapter_title):
                    current_chapter["title"] = chapter_title
                    chapter_titles.append(current_chapter["title"])
                else:
                    current_chapter["title"] = "blank"
                    chapter_titles.append("blank")
            elif line:
                if not initialized_first_chapter:
                    chapter_titles.append("blank")
                    initialized_first_chapter = True
                if any(char.isalnum() for char in line):
                    sentences = sent_tokenize(line)
                    cleaned_sentences = [s for s in sentences if any(char.isalnum() for char in s)]
                    line = " ".join(cleaned_sentences)
                    current_chapter["paragraphs"].append(line)

        if current_chapter["paragraphs"]:
            book_contents.append(current_chapter)

    return book_contents, book_title, book_author, chapter_titles


def validate_text_file(
    sourcefile: str,
    book_title: str,
    book_author: str,
    book_contents: list[dict[str, Any]],
) -> None:
    """Validate that the parsed text file has Title, Author, and at least one chapter break.

    Raises ``SystemExit(1)`` with an explanatory log message if any are missing.
    """
    errors: list[str] = []

    if book_title == sourcefile:
        errors.append("- Missing 'Title:' line at the beginning of the file")

    if book_author == "Unknown":
        errors.append("- Missing 'Author:' line at the beginning of the file")

    has_chapter_break = False
    with open(sourcefile, "r", encoding="utf-8") as file:
        for line in file:
            if line.strip().startswith("#"):
                has_chapter_break = True
                break

    if not has_chapter_break:
        errors.append("- Missing at least one chapter break line starting with '#'")

    if errors:
        bar = "=" * 70
        message = (
            f"\n{bar}\n"
            "ERROR: Text file validation failed\n"
            f"{bar}\n\n"
            "The text file must contain the following elements:\n\n"
            "1. A 'Title:' line at the beginning (e.g., 'Title: My Book')\n"
            "2. An 'Author:' line at the beginning (e.g., 'Author: John Doe')\n"
            "3. At least one chapter break line starting with '#' (e.g., '# Chapter 1')\n\n"
            "Missing elements:\n"
            + "\n".join(errors)
            + "\n\n"
            "Please correct the text file format and try again.\n"
            f"{bar}"
        )
        logger.error(message)
        sys.exit(1)
