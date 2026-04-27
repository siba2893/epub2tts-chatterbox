"""Pydantic models for the web UI backend."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class JobState(str, Enum):
    QUEUED = "queued"
    UPLOADED = "uploaded"
    NAMING = "naming"
    EDITING = "editing"
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UploadResponse(BaseModel):
    job_id: str
    title: str
    author: str
    chapter_count: int


class JobStatus(BaseModel):
    job_id: str
    state: JobState
    title: str | None = None
    author: str | None = None
    error: str | None = None
    chapters_total: int = 0
    chapters_done: int = 0
    current_chapter: int | None = None
    current_paragraph: int | None = None
    elapsed_seconds: float = 0.0
    eta_seconds: float | None = None


class ChapterPreviewRow(BaseModel):
    """One sample chapter rendered under each naming method."""
    toc: str | None = None
    heading: str | None = None
    class_: str | None = Field(default=None, alias="class")
    fallback: str | None = None

    model_config = {"populate_by_name": True}


class ChapterPreviewResponse(BaseModel):
    rows: list[ChapterPreviewRow]


class NamingChoice(BaseModel):
    method: Literal["auto", "toc", "heading", "class", "fallback"]


class ChapterEdit(BaseModel):
    title: str
    paragraphs: list[str]


class TextDocument(BaseModel):
    title: str
    author: str
    chapters: list[ChapterEdit]


class Settings(BaseModel):
    """TTS / pipeline tunables forwarded to the CLI as flags."""
    paragraph_pause_ms: int = 600
    min_sentence_words: int = 8
    exaggeration: float = 0.7
    cfg_weight: float = 0.4
    retry_count: int = 3
    sample_path: str | None = None
    cover_path: str | None = None
    notitles: bool = False
    language: str = "en"
    # Optional absolute path to a folder where the final .m4b will be copied
    # after a successful run. Resume state (partN.flac etc.) stays in the
    # per-job workdir regardless.
    output_dir: str | None = None


class StartRequest(BaseModel):
    settings: Settings = Settings()


class ResumeState(BaseModel):
    completed_chapters: int
    total_chapters: int
    completed_titles: list[str]


class LibraryEntry(BaseModel):
    filename: str
    title: str | None = None
    author: str | None = None
    cover_url: str | None = None
    duration_seconds: float | None = None
    size_bytes: int


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = "1.0.0"
