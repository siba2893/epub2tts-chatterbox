"""FastAPI app for the epub2tts-chatterbox web UI."""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

# Allow `python -m epub2tts_chatterbox.epub_export` style imports from the
# project root regardless of where uvicorn is launched.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from epub2tts_chatterbox.epub_export import (  # noqa: E402
    build_toc_map,
    export_epub,
    get_chapter_titles_by_method,
)
from epub2tts_chatterbox.text_utils import get_book  # noqa: E402
from ebooklib import epub  # noqa: E402

from .jobs import JOBS_ROOT, cancel_job, registry, resume_state, start_job
from .schemas import (
    ChapterPreviewResponse,
    ChapterPreviewRow,
    HealthResponse,
    JobState,
    JobStatus,
    LibraryEntry,
    NamingChoice,
    ResumeState,
    Settings,
    StartRequest,
    TextDocument,
    UploadResponse,
)


app = FastAPI(title="epub2tts-chatterbox web UI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


# ---------------------------------------------------------------------------
# Upload + naming
# ---------------------------------------------------------------------------

@app.post("/api/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only .epub files are accepted")

    job = registry.create()
    epub_path = job.workdir / "source.epub"
    with epub_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        book = epub.read_epub(str(epub_path))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse EPUB: {e}") from e

    title_meta = book.get_metadata("DC", "title")
    author_meta = book.get_metadata("DC", "creator")
    title = title_meta[0][0] if title_meta else "Unknown Title"
    author = author_meta[0][0] if author_meta else "Unknown Author"

    job.title = title
    job.author = author
    job.state = JobState.UPLOADED

    spine_count = sum(1 for s in book.spine if s[1] == "yes")
    return UploadResponse(
        job_id=job.job_id, title=title, author=author, chapter_count=spine_count
    )


@app.get("/api/jobs/{job_id}/naming-preview", response_model=ChapterPreviewResponse)
def naming_preview(job_id: str, max_samples: int = 6) -> ChapterPreviewResponse:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    epub_path = job.workdir / "source.epub"
    if not epub_path.exists():
        raise HTTPException(status_code=404, detail="EPUB not on disk for this job")

    book = epub.read_epub(str(epub_path))
    toc_map = build_toc_map(getattr(book, "toc", []))
    spine_ids = [s[0] for s in book.spine if s[1] == "yes"]
    items = {item.get_id(): item for item in book.get_items()}

    rows: list[ChapterPreviewRow] = []
    for sid in spine_ids:
        if len(rows) >= max_samples:
            break
        item = items.get(sid)
        if item is None:
            continue
        content = item.get_content()
        if len(content) < 100:
            continue
        titles = get_chapter_titles_by_method(
            content, item_name=item.get_name(), item_id=sid, toc_map=toc_map
        )
        rows.append(
            ChapterPreviewRow.model_validate(
                {
                    "toc": titles.get("toc"),
                    "heading": titles.get("heading"),
                    "class": titles.get("class"),
                    "fallback": titles.get("fallback"),
                }
            )
        )
    return ChapterPreviewResponse(rows=rows)


@app.post("/api/jobs/{job_id}/naming")
def choose_naming(job_id: str, choice: NamingChoice) -> dict[str, Any]:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    epub_path = job.workdir / "source.epub"
    if not epub_path.exists():
        raise HTTPException(status_code=404, detail="EPUB not on disk for this job")

    txt_path = job.workdir / "book.txt"
    export_epub(
        str(epub_path),
        output_path=str(txt_path),
        naming_method=choice.method,
        verbose=False,
        interactive=False,
    )
    job.naming_method = choice.method
    job.state = JobState.EDITING
    return {"job_id": job.job_id, "txt_path": str(txt_path), "method": choice.method}


# ---------------------------------------------------------------------------
# Text editor round-trip
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}/text", response_model=TextDocument)
def get_text(job_id: str) -> TextDocument:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    txt_path = job.workdir / "book.txt"
    if not txt_path.exists():
        raise HTTPException(
            status_code=404, detail="No text yet — pick a naming method first"
        )
    contents, title, author, _ = get_book(str(txt_path))
    return TextDocument(
        title=title,
        author=author,
        chapters=[
            {"title": c.get("title") or "", "paragraphs": c.get("paragraphs", [])}
            for c in contents
        ],
    )


@app.put("/api/jobs/{job_id}/text", response_model=TextDocument)
def put_text(job_id: str, doc: TextDocument) -> TextDocument:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    txt_path = job.workdir / "book.txt"

    lines: list[str] = []
    lines.append(f"Title: {doc.title}")
    lines.append(f"Author: {doc.author}")
    lines.append("")
    for chapter in doc.chapters:
        title = chapter.title.strip() or "blank"
        lines.append(f"# {title}")
        lines.append("")
        for paragraph in chapter.paragraphs:
            text = paragraph.strip()
            if text:
                lines.append(text)
                lines.append("")
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    job.title = doc.title
    job.author = doc.author
    job.chapters_total = len(doc.chapters)
    return doc


# ---------------------------------------------------------------------------
# Run / cancel / status
# ---------------------------------------------------------------------------

@app.post("/api/jobs/{job_id}/start", response_model=JobStatus)
def start(job_id: str, req: StartRequest) -> JobStatus:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.state == JobState.RUNNING and job.process and job.process.poll() is None:
        # Already running — return current snapshot instead of spawning a duplicate.
        return _job_status(job)
    txt_path = job.workdir / "book.txt"
    if not txt_path.exists():
        raise HTTPException(status_code=400, detail="No text file to convert")

    job.settings = req.settings
    start_job(job, txt_path)
    return _job_status(job)


@app.post("/api/jobs/{job_id}/cancel", response_model=JobStatus)
def cancel(job_id: str) -> JobStatus:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    cancel_job(job)
    return _job_status(job)


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str) -> JobStatus:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_status(job)


@app.get("/api/jobs/{job_id}/resume-state", response_model=ResumeState)
def get_resume_state(job_id: str) -> ResumeState:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return ResumeState(**resume_state(job))


def _job_status(job: Any) -> JobStatus:
    return JobStatus(
        job_id=job.job_id,
        state=job.state,
        title=job.title,
        author=job.author,
        error=job.error,
        chapters_total=job.chapters_total,
        chapters_done=job.chapters_done,
        current_chapter=job.current_chapter,
        current_paragraph=job.current_paragraph,
        elapsed_seconds=job.elapsed_seconds,
        eta_seconds=job.eta_seconds,
    )


# ---------------------------------------------------------------------------
# SSE event stream
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}/events")
async def events(job_id: str):
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    queue = job.subscribe()

    async def event_gen():
        try:
            while True:
                if job.state in (JobState.DONE, JobState.FAILED, JobState.CANCELLED):
                    if queue.empty():
                        # Drain a final state event then stop.
                        yield f"data: {json.dumps({'type': 'state', 'state': job.state.value})}\n\n"
                        return
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            job.unsubscribe(queue)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

@app.get("/api/library", response_model=list[LibraryEntry])
def library() -> list[LibraryEntry]:
    entries: list[LibraryEntry] = []
    for job_dir in sorted(JOBS_ROOT.glob("*")):
        for m4b in sorted(job_dir.glob("*.m4b")):
            title: str | None = m4b.stem
            author: str | None = None
            duration: float | None = None
            try:
                from mutagen import mp4 as _mp4

                tags = _mp4.MP4(str(m4b))
                if tags.tags:
                    title = (tags.tags.get("\xa9nam") or [title])[0]
                    author = (tags.tags.get("\xa9ART") or [None])[0]
                if tags.info is not None:
                    duration = float(tags.info.length)
            except Exception:
                pass
            entries.append(
                LibraryEntry(
                    filename=str(m4b.relative_to(JOBS_ROOT)),
                    title=title,
                    author=author,
                    duration_seconds=duration,
                    size_bytes=m4b.stat().st_size,
                )
            )
    return entries


# ---------------------------------------------------------------------------
# Per-chapter preview + re-render
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}/chapters")
def list_chapters(job_id: str) -> dict[str, Any]:
    """Return on-disk chapter completion state for a job."""
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    parts = sorted(
        job.workdir.glob("part*.flac"),
        key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0),
    )
    items = [
        {
            "index": int("".join(c for c in p.stem if c.isdigit()) or 0),
            "size_bytes": p.stat().st_size,
            "filename": p.name,
        }
        for p in parts
    ]
    return {"job_id": job_id, "completed": items, "total": job.chapters_total}


@app.get("/api/jobs/{job_id}/chapter/{n}/audio")
def chapter_audio(job_id: str, n: int):
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    flac = job.workdir / f"part{n}.flac"
    if not flac.exists():
        raise HTTPException(status_code=404, detail=f"part{n}.flac not on disk")
    return FileResponse(str(flac), media_type="audio/flac", filename=flac.name)


@app.post("/api/jobs/{job_id}/chapter/{n}/rerun", response_model=JobStatus)
def rerun_chapter(job_id: str, n: int) -> JobStatus:
    """Delete partN.flac and re-run; the resume logic skips all other chapters."""
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.state == JobState.RUNNING and job.process and job.process.poll() is None:
        raise HTTPException(
            status_code=409,
            detail="A conversion is already running. Cancel it before re-rendering.",
        )
    flac = job.workdir / f"part{n}.flac"
    if flac.exists():
        flac.unlink()
    txt_path = job.workdir / "book.txt"
    if not txt_path.exists():
        raise HTTPException(status_code=400, detail="No text file to convert")
    start_job(job, txt_path)
    return _job_status(job)


# ---------------------------------------------------------------------------
# Voice samples
# ---------------------------------------------------------------------------

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/api/samples")
async def upload_sample(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith((".wav", ".mp3", ".flac")):
        raise HTTPException(status_code=400, detail="Sample must be .wav, .mp3, or .flac")
    safe_name = Path(file.filename).name
    target = SAMPLES_DIR / safe_name
    with target.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"filename": safe_name, "size_bytes": target.stat().st_size}


@app.get("/api/samples")
def list_samples() -> list[dict[str, Any]]:
    return [
        {
            "filename": p.name,
            "size_bytes": p.stat().st_size,
            "url": f"/api/samples/{p.name}",
            "path": str(p),
        }
        for p in sorted(SAMPLES_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in (".wav", ".mp3", ".flac")
    ]


@app.get("/api/samples/{name}")
def get_sample(name: str):
    safe = Path(name).name  # strip path components
    target = SAMPLES_DIR / safe
    if not target.exists():
        raise HTTPException(status_code=404, detail="Sample not found")
    return FileResponse(str(target), media_type="audio/wav", filename=safe)
