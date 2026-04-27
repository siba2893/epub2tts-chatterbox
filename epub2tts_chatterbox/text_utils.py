"""Pure text/formatting utilities used by the TTS pipeline.

Kept free of heavy imports (torch, chatterbox) so they can be unit-tested
without a GPU or model download.
"""
import re

from nltk.tokenize import sent_tokenize


def conditional_sentence_case(sent):
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


def format_time_adaptive(seconds):
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


def sort_key(s):
    """Sort key that extracts the first integer in a filename like 'sntnc12.wav'."""
    return int(re.findall(r"\d+", s)[0])


def combine_short_paragraphs(paragraphs, min_words=6):
    """Merge a single-sentence paragraph shorter than ``min_words`` into the next one."""
    if not paragraphs:
        return []

    result = []
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


def combine_short_sentences(sentences, min_words=6, keep_threshold=8):
    """Combine short sentences within a paragraph.

    Sentences with >= ``keep_threshold`` words pass through unchanged; shorter
    runs are merged until they reach ``min_words``. Trailing remainder is
    appended to the previous chunk if it is itself shorter than ``min_words``.
    """
    if not sentences:
        return []

    result = []
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
