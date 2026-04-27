"""In-memory job registry and conversion orchestration.

Each job has its own working directory under ``webui/backend/jobs/<job_id>/``
where the EPUB, derived .txt, intermediate ``partN.flac`` files, and final
M4B all live. The CLI is invoked as a subprocess so the existing pipeline is
reused unchanged; progress is parsed from the logger output line by line.
"""
from __future__ import annotations

import asyncio
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schemas import JobState, Settings


JOBS_ROOT = Path(__file__).resolve().parent / "jobs"
JOBS_ROOT.mkdir(parents=True, exist_ok=True)


@dataclass
class Job:
    job_id: str
    workdir: Path
    state: JobState = JobState.QUEUED
    title: str | None = None
    author: str | None = None
    chapters_total: int = 0
    chapters_done: int = 0
    current_chapter: int | None = None
    current_paragraph: int | None = None
    started_at: float | None = None
    error: str | None = None
    process: subprocess.Popen[str] | None = None
    settings: Settings = field(default_factory=Settings)
    naming_method: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    _subscribers: list[asyncio.Queue[dict[str, Any]]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        return time.time() - self.started_at

    @property
    def eta_seconds(self) -> float | None:
        if not self.chapters_done or not self.chapters_total:
            return None
        per_chapter = self.elapsed_seconds / max(self.chapters_done, 1)
        remaining = self.chapters_total - self.chapters_done
        return per_chapter * remaining if remaining > 0 else 0.0

    def emit(self, event: dict[str, Any]) -> None:
        """Record an event and broadcast it to live SSE subscribers."""
        with self._lock:
            self.events.append(event)
            queues = list(self._subscribers)
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1024)
        with self._lock:
            # Replay backlog so a late subscriber sees everything so far.
            for event in self.events:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    break
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self) -> Job:
        job_id = uuid.uuid4().hex[:12]
        workdir = JOBS_ROOT / job_id
        workdir.mkdir(parents=True, exist_ok=True)
        job = Job(job_id=job_id, workdir=workdir)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())


registry = JobRegistry()


# ---------------------------------------------------------------------------
# Progress parsing
# ---------------------------------------------------------------------------

CHAPTER_RE = re.compile(
    r"Chapter \((?P<idx>\d+)/(?P<total>\d+)\): (?P<title>.+?)(?: \| Elapsed| $)"
)
DEVICE_RE = re.compile(r"Attempting to use device: (?P<device>\w+)")


def parse_progress_line(line: str) -> dict[str, Any] | None:
    """Translate a single CLI logger line into a structured event, if any."""
    line = line.rstrip()
    if not line:
        return None
    m = CHAPTER_RE.search(line)
    if m:
        return {
            "type": "chapter",
            "index": int(m.group("idx")),
            "total": int(m.group("total")),
            "title": m.group("title").strip(),
        }
    m = DEVICE_RE.search(line)
    if m:
        return {"type": "device", "device": m.group("device")}
    if "exists, skipping to next chapter" in line:
        return {"type": "skip_chapter", "raw": line}
    if "ERROR" in line or "FAILURE" in line:
        return {"type": "error", "raw": line}
    return {"type": "log", "raw": line}


def build_cli_command(workdir: Path, txt_path: Path, settings: Settings) -> list[str]:
    """Build the subprocess argv for invoking the existing CLI."""
    argv: list[str] = [
        sys.executable,
        "-u",  # unbuffered stdout for line-by-line progress
        "-m",
        "epub2tts_chatterbox.epub2tts_chatterbox",
        str(txt_path),
        "--paragraph-pause-ms",
        str(settings.paragraph_pause_ms),
        "--min-sentence-words",
        str(settings.min_sentence_words),
        "--exaggeration",
        str(settings.exaggeration),
        "--cfg_weight",
        str(settings.cfg_weight),
        "--retry-count",
        str(settings.retry_count),
        "--language",
        settings.language,
    ]
    if settings.sample_path:
        argv += ["--sample", settings.sample_path]
    if settings.cover_path:
        argv += ["--cover", settings.cover_path]
    if settings.notitles:
        argv.append("--notitles")
    return argv


def run_subprocess_blocking(job: Job, txt_path: Path) -> None:
    """Run the CLI subprocess to completion; emit events as lines arrive."""
    argv = build_cli_command(job.workdir, txt_path, job.settings)
    job.started_at = time.time()
    job.state = JobState.RUNNING
    job.emit({"type": "state", "state": job.state.value})

    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(job.workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        job.process = proc
    except FileNotFoundError as e:
        job.state = JobState.FAILED
        job.error = f"Failed to launch CLI: {e}"
        job.emit({"type": "state", "state": job.state.value, "error": job.error})
        return

    assert proc.stdout is not None
    for line in proc.stdout:
        evt = parse_progress_line(line)
        if evt is None:
            continue
        if evt["type"] == "chapter":
            job.current_chapter = evt["index"]
            job.chapters_total = evt["total"]
        elif evt["type"] == "skip_chapter":
            job.chapters_done += 1
        job.emit(evt)

    rc = proc.wait()
    if rc == 0:
        job.state = JobState.DONE
        job.chapters_done = job.chapters_total
    elif job.state == JobState.CANCELLED:
        pass
    else:
        job.state = JobState.FAILED
        job.error = f"CLI exited with code {rc}"
    job.emit({
        "type": "state",
        "state": job.state.value,
        "error": job.error,
        "exit_code": rc,
    })


def start_job(job: Job, txt_path: Path) -> None:
    """Launch the conversion in a daemon thread."""
    t = threading.Thread(
        target=run_subprocess_blocking, args=(job, txt_path), daemon=True
    )
    t.start()


def cancel_job(job: Job) -> bool:
    if job.process is None or job.process.poll() is not None:
        return False
    job.state = JobState.CANCELLED
    try:
        job.process.terminate()
    except OSError:
        return False
    job.emit({"type": "state", "state": job.state.value})
    return True


def resume_state(job: Job) -> dict[str, Any]:
    """Inspect the working dir for partN.flac files to compute resume status."""
    parts = sorted(job.workdir.glob("part*.flac"))
    completed_titles: list[str] = []
    return {
        "completed_chapters": len(parts),
        "total_chapters": job.chapters_total,
        "completed_titles": completed_titles,
    }
