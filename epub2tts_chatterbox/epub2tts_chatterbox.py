import os
import sys
# Automatically enable MPS fallback on Apple Silicon macOS
# But prob not, see https://github.com/resemble-ai/chatterbox/blob/master/example_for_mac.py
if sys.platform == 'darwin':
    os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
import argparse
import logging
import time
import numpy as np
import re
import soundfile
import subprocess
import torch
import warnings
from tqdm import tqdm
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub
import soundfile as sf
from lxml import etree
from mutagen import mp4
import nltk
from nltk.tokenize import sent_tokenize
from PIL import Image
from pydub import AudioSegment
import zipfile
import warnings

# Import EPUB export functions from the reusable library module
from epub2tts_chatterbox.epub_export import (
    export_epub,
    export_epub_to_dict,
    build_toc_map,
    get_chapter_titles_by_method,
    extract_chapter_content,
    get_epub_cover,
    preview_chapter_names,
    export,
)
from epub2tts_chatterbox.text_utils import (
    combine_short_paragraphs,
    combine_short_sentences,
    conditional_sentence_case,
    format_time_adaptive,
    get_book,
    sort_key,
    validate_text_file,
)

warnings.filterwarnings("ignore")

namespaces = {
   "calibre":"http://calibre.kovidgoyal.net/2009/metadata",
   "dc":"http://purl.org/dc/elements/1.1/",
   "dcterms":"http://purl.org/dc/terms/",
   "opf":"http://www.idpf.org/2007/opf",
   "u":"urn:oasis:names:tc:opendocument:xmlns:container",
   "xsi":"http://www.w3.org/2001/XMLSchema-instance",
}

warnings.filterwarnings("ignore", module="ebooklib.epub")

logger = logging.getLogger("epub2tts_chatterbox")


def _setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging for the CLI. ``verbose`` enables DEBUG, ``quiet`` raises to WARNING."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    fmt = "%(asctime)s %(levelname)s %(message)s" if verbose else "%(message)s"
    logging.basicConfig(level=level, format=fmt, force=True)


def ensure_punkt():
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt")
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab")

def check_for_file(filename):
    if os.path.isfile(filename):
        print(f"The file '{filename}' already exists.")
        overwrite = input("Do you want to overwrite the file? (y/n): ")
        if overwrite.lower() != 'y':
            print("Exiting without overwriting the file.")
            sys.exit()
        else:
            os.remove(filename)

def append_silence(tempfile, duration=1200):
    if not os.path.isfile(tempfile):
        logger.warning("File %s does not exist, skipping silence append.", tempfile)
        return
    audio = AudioSegment.from_file(tempfile)
    # Create a silence segment
    silence = AudioSegment.silent(duration)
    # Append the silence segment to the audio
    combined = audio + silence
    # Save the combined audio back to file
    combined.export(tempfile, format="flac")

def chatterbox_read(sentences, sample, filenames, model, exaggeration, cfg_weight, language="en", max_attempts=3):
    for i, sent in enumerate(sentences):
        clean_sent = conditional_sentence_case(sent.strip())
        for attempt in range(1, max_attempts + 1):
            try:
                if sample == "none":
                    if language != "en":
                        wav = model.generate(clean_sent, language_id=language)
                    else:
                        wav = model.generate(clean_sent)
                else:
                    if language != "en":
                        wav = model.generate(clean_sent, audio_prompt_path=sample, language_id=language)
                    else:
                        wav = model.generate(clean_sent, audio_prompt_path=sample, exaggeration=exaggeration, cfg_weight=cfg_weight)

                ta.save(filenames[i], wav, model.sr)
                if not os.path.isfile(filenames[i]):
                    raise FileNotFoundError(f"File {filenames[i]} was not created.")
                break

            except Exception as e:
                if attempt < max_attempts:
                    logger.warning("Attempt %d failed for sentence %r: %s -- retrying...", attempt, clean_sent, e)
                else:
                    logger.error("Failed to process sentence %r after %d attempts: %s", clean_sent, max_attempts, e)

def read_book(book_contents, sample, notitles, exaggeration, cfg_weight, language="en",
              paragraph_pause_ms=600, min_sentence_words=8, max_attempts=3):
    # Automatically detect the best available device
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    current_device = torch.device(device)
    logger.info("Attempting to use device: %s", device)

    use_multilingual = language != "en"
    if use_multilingual:
        logger.info("Loading ChatterboxMultilingualTTS for language: %s", language)
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    else:
        model = ChatterboxTTS.from_pretrained(device=device)

    start_time = time.time()
    total_chars = sum(len(''.join(chapter['paragraphs'])) for chapter in book_contents)
    processed_chars = 0

    segments = []
    for i, chapter in enumerate(book_contents, start=1):
        files = []
        partname = f"part{i}.flac"

        if os.path.isfile(partname):
            logger.info("%s exists, skipping to next chapter", partname)
            segments.append(partname)
            processed_chars += len(''.join(chapter['paragraphs']))
        else:
            elapsed_time = time.time() - start_time
            elapsed_str = format_time_adaptive(elapsed_time)

            if processed_chars > 0:
                time_per_char = elapsed_time / processed_chars
                remaining_chars = total_chars - processed_chars
                eta_seconds = remaining_chars * time_per_char
                eta_str = format_time_adaptive(eta_seconds)
                timing_info = f" | Elapsed: {elapsed_str} | ETA: {eta_str}"
            else:
                timing_info = f" | Elapsed: {elapsed_str}"

            logger.info("Chapter (%d/%d): %s%s", i, len(book_contents), chapter['title'], timing_info)
            if chapter["title"] == "":
                chapter["title"] = "blank"
            if chapter["title"] != "Title" and notitles != True:
                chapter['paragraphs'][0] = chapter['title'] + ". " + chapter['paragraphs'][0]

            combined_paragraphs = combine_short_paragraphs(chapter["paragraphs"])

            for pindex, paragraph in enumerate(combined_paragraphs):
                # Scope the paragraph filename by chapter index so a stale file
                # left over from a previous chapter's cleanup window cannot be
                # mistaken for this chapter's paragraph N (correctness fix for
                # a narrow crash window between os.replace(partN) and the
                # pgraphs cleanup loop below).
                ptemp = f"pgraphs{i}_{pindex}.flac"
                if os.path.isfile(ptemp):
                    logger.debug("%s exists, skipping to next paragraph", ptemp)
                else:
                    sentences = sent_tokenize(paragraph)
                    sentences = combine_short_sentences(sentences, keep_threshold=min_sentence_words)
                    filenames = [
                        "sntnc" + str(z) + ".wav" for z in range(len(sentences))
                    ]
                    chatterbox_read(sentences, sample, filenames, model, exaggeration, cfg_weight, language, max_attempts=max_attempts)
                    append_silence(filenames[-1], paragraph_pause_ms)
                    sorted_files = sorted(filenames, key=sort_key)
                    combined = AudioSegment.empty()
                    for file in sorted_files:
                        try:
                            combined += AudioSegment.from_file(file)
                        except (OSError, FileNotFoundError, RuntimeError) as e:
                            logger.error("FAILURE at sorted file combine for %s (sorted=%s, unsorted=%s): %s",
                                         file, sorted_files, filenames, e)
                            sys.exit(1)
                    ptemp_tmp = ptemp + ".tmp"
                    combined.export(ptemp_tmp, format="flac")
                    os.replace(ptemp_tmp, ptemp)
                    for file in sorted_files:
                        os.remove(file)
                files.append(ptemp)
            # combine paragraphs into chapter
            append_silence(files[-1], 2000)
            combined = AudioSegment.empty()
            for file in files:
                combined += AudioSegment.from_file(file)
            partname_tmp = partname + ".tmp"
            combined.export(partname_tmp, format="flac")
            os.replace(partname_tmp, partname)
            for file in files:
                os.remove(file)
            segments.append(partname)
            # Track processed characters for this chapter
            processed_chars += len(''.join(chapter['paragraphs']))
    return segments

def generate_metadata(files, author, title, chapter_titles):
    chap = 0
    start_time = 0
    with open("FFMETADATAFILE", "w") as file:
        file.write(";FFMETADATA1\n")
        file.write(f"ARTIST={author}\n")
        file.write(f"ALBUM={title}\n")
        file.write(f"TITLE={title}\n")
        file.write("DESCRIPTION=Made with https://github.com/aedocw/epub2tts-chatterbox\n")
        for file_name in files:
            duration = get_duration(file_name)
            file.write("[CHAPTER]\n")
            file.write("TIMEBASE=1/1000\n")
            file.write(f"START={start_time}\n")
            file.write(f"END={start_time + duration}\n")
            file.write(f"title={chapter_titles[chap]}\n")
            chap += 1
            start_time += duration

def get_duration(file_path):
    audio = AudioSegment.from_file(file_path)
    duration_milliseconds = len(audio)
    return duration_milliseconds

def _run_ffmpeg(cmd, step_description):
    """Run an ffmpeg subprocess and surface a clear error if it fails."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as e:
        logger.error("ffmpeg not found on PATH while trying to %s.", step_description)
        raise SystemExit(1) from e
    except subprocess.CalledProcessError as e:
        logger.error("ffmpeg failed during step '%s' (exit %d).", step_description, e.returncode)
        if e.stderr:
            tail = "\n".join(e.stderr.strip().splitlines()[-20:])
            logger.error("ffmpeg stderr (last 20 lines):\n%s", tail)
        raise SystemExit(1) from e


def _quiet_remove(path):
    """Best-effort os.remove that silently ignores files that don't exist."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def make_m4b(files, sourcefile, speaker):
    filelist = "filelist.txt"
    speaker_file = os.path.basename(speaker)
    basefile = sourcefile.replace(".txt", "")
    outputm4a = f"{basefile}.m4a"
    outputm4b = f"{basefile} ({speaker_file.split('.wav')[0]}).m4b"

    try:
        with open(filelist, "w") as f:
            for filename in files:
                filename = filename.replace("'", "'\\''")
                f.write(f"file '{filename}'\n")
        _run_ffmpeg(
            [
                "ffmpeg", "-f", "concat", "-safe", "0", "-i", filelist,
                "-codec:a", "flac", "-f", "mp4", "-strict", "-2", outputm4a,
            ],
            "concat to m4a",
        )
        _run_ffmpeg(
            [
                "ffmpeg", "-i", outputm4a, "-i", "FFMETADATAFILE",
                "-map_metadata", "1", "-codec", "aac", outputm4b,
            ],
            "encode m4b with metadata",
        )
    finally:
        # Always clean scratch intermediates; if a run crashed, this keeps the
        # working directory tidy without touching the caller's resume state.
        for path in (filelist, "FFMETADATAFILE", outputm4a):
            _quiet_remove(path)

    # Inputs (partN.flac) are the resume state; only remove on success.
    for f in files:
        _quiet_remove(f)
    return outputm4b

def add_cover(cover_img, filename):
    if not cover_img:
        return
    if not os.path.isfile(cover_img):
        logger.warning("Cover image %s not found", cover_img)
        return
    try:
        m4b = mp4.MP4(filename)
        with open(cover_img, "rb") as f:
            cover_image = f.read()
        m4b["covr"] = [mp4.MP4Cover(cover_image)]
        m4b.save()
    except (OSError, mp4.MP4StreamInfoError) as e:
        logger.warning("Failed to embed cover image %s: %s", cover_img, e)

def main():
    parser = argparse.ArgumentParser(
        prog="epub2tts-chatterbox",
        description="Read a text file to audiobook format",
    )
    parser.add_argument("sourcefile", type=str, help="The epub or text file to process")
    parser.add_argument(
        "--sample",
        type=str,
        help="Sample wav file to use for voice cloning",
    )
    parser.add_argument(
        "--cover",
        type=str,
        help="jpg image to use for cover",
    )
    parser.add_argument(
        "--notitles",
        action="store_true",
        help="Do not read chapter titles"
    )
    parser.add_argument(
        "--exaggeration",
        type=float,
        default=0.7,
        help="Exaggeration factor for voice cloning (default: 0.7)",
    )
    parser.add_argument(
        "--cfg_weight",
        type=float,
        default=0.4,
        help="CFG weight for voice cloning (default: 0.4)",
    )
    parser.add_argument(
        "--naming",
        type=str,
        choices=['auto', 'toc', 'heading', 'class', 'fallback'],
        default=None,
        help="Chapter naming method: auto (default, shows preview), toc, heading, class, or fallback",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        help=(
            "Language code for multilingual TTS (default: en). "
            "When set to anything other than 'en', uses ChatterboxMultilingualTTS. "
            "Supported: ar, da, de, el, en, es, fi, fr, he, hi, it, ja, ko, ms, nl, no, pl, pt, ru, sv, sw, tr, zh"
        ),
    )
    parser.add_argument(
        "--paragraph-pause-ms",
        type=int,
        default=600,
        help="Silence inserted between paragraphs, in milliseconds (default: 600)",
    )
    parser.add_argument(
        "--min-sentence-words",
        type=int,
        default=8,
        help="Sentences with at least this many words pass through alone; shorter ones are merged (default: 8)",
    )
    parser.add_argument(
        "--retry-count",
        type=int,
        default=3,
        help="Number of times to retry a sentence if TTS generation fails (default: 3)",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="Enable DEBUG logging")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="Only log warnings and errors")

    args = parser.parse_args()
    _setup_logging(verbose=args.verbose, quiet=args.quiet)
    logger.debug("Parsed args: %s", args)

    ensure_punkt()

    if args.sourcefile.endswith(".epub"):
        book = epub.read_epub(args.sourcefile)
        export(book, args.sourcefile, naming_method=args.naming)
        return

    book_contents, book_title, book_author, chapter_titles = get_book(args.sourcefile)

    validate_text_file(args.sourcefile, book_title, book_author, book_contents)
    sample = args.sample if args.sample is not None else "none"
    files = read_book(
        book_contents,
        sample,
        args.notitles,
        args.exaggeration,
        args.cfg_weight,
        args.language,
        paragraph_pause_ms=args.paragraph_pause_ms,
        min_sentence_words=args.min_sentence_words,
        max_attempts=args.retry_count,
    )
    generate_metadata(files, book_author, book_title, chapter_titles)
    m4bfilename = make_m4b(files, args.sourcefile, sample)
    add_cover(args.cover, m4bfilename)
    
if __name__ == "__main__":
    main()
