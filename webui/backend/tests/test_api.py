"""Smoke tests for the FastAPI web UI backend."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from webui.backend import app as app_module
from webui.backend.app import app
from webui.backend.jobs import parse_progress_line


FIXTURE_EPUB = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "sample.epub"


@pytest.fixture(autouse=True)
def _isolate_samples_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect sample uploads to a per-test tmp dir so tests can't leak files."""
    tmp_samples = tmp_path / "samples"
    tmp_samples.mkdir()
    monkeypatch.setattr(app_module, "SAMPLES_DIR", tmp_samples)
    return tmp_samples


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_health_ok(self, client: TestClient):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestUploadAndNaming:
    @pytest.fixture(scope="class")
    def uploaded_job(self, client: TestClient) -> str:
        assert FIXTURE_EPUB.exists(), f"fixture missing at {FIXTURE_EPUB}"
        with FIXTURE_EPUB.open("rb") as f:
            r = client.post(
                "/api/upload",
                files={"file": ("sample.epub", f, "application/epub+zip")},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["job_id"]
        assert body["title"] == "Smoke Test Book"
        assert body["author"] == "Test Author"
        assert body["chapter_count"] >= 1
        return body["job_id"]

    def test_rejects_non_epub(self, client: TestClient):
        r = client.post(
            "/api/upload",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 400

    def test_naming_preview_rows(self, client: TestClient, uploaded_job: str):
        r = client.get(f"/api/jobs/{uploaded_job}/naming-preview")
        assert r.status_code == 200
        rows = r.json()["rows"]
        assert isinstance(rows, list)
        assert len(rows) >= 1
        # Each row should have all four method keys present (values may be null).
        for row in rows:
            assert set(row.keys()) >= {"toc", "heading", "class", "fallback"}

    def test_naming_choice_writes_text(self, client: TestClient, uploaded_job: str):
        r = client.post(
            f"/api/jobs/{uploaded_job}/naming",
            json={"method": "toc"},
        )
        assert r.status_code == 200
        assert r.json()["method"] == "toc"

    def test_text_round_trip(self, client: TestClient, uploaded_job: str):
        # First, ensure naming step ran so a .txt exists.
        client.post(f"/api/jobs/{uploaded_job}/naming", json={"method": "toc"})

        r = client.get(f"/api/jobs/{uploaded_job}/text")
        assert r.status_code == 200
        doc = r.json()
        assert doc["title"]
        assert doc["author"]
        assert isinstance(doc["chapters"], list)
        assert len(doc["chapters"]) >= 1

        # Round-trip: PUT the same shape back.
        r = client.put(f"/api/jobs/{uploaded_job}/text", json=doc)
        assert r.status_code == 200
        assert r.json()["title"] == doc["title"]


class TestJobStatus:
    def test_status_for_unknown_job_404(self, client: TestClient):
        r = client.get("/api/jobs/does-not-exist")
        assert r.status_code == 404


class TestProgressParser:
    def test_chapter_line_parses(self):
        line = "Chapter (3/12): The Forest | Elapsed: 2m 5s | ETA: 7m 14s"
        evt = parse_progress_line(line)
        assert evt == {
            "type": "chapter",
            "index": 3,
            "total": 12,
            "title": "The Forest",
        }

    def test_device_line_parses(self):
        evt = parse_progress_line("Attempting to use device: cuda")
        assert evt == {"type": "device", "device": "cuda"}

    def test_skip_chapter_line(self):
        evt = parse_progress_line("part4.flac exists, skipping to next chapter")
        assert evt is not None and evt["type"] == "skip_chapter"

    def test_blank_line_returns_none(self):
        assert parse_progress_line("") is None
        assert parse_progress_line("   \n") is None

    def test_unrecognized_line_is_log(self):
        evt = parse_progress_line("Loading some random library...")
        assert evt is not None and evt["type"] == "log"

    def test_error_line_classified(self):
        evt = parse_progress_line("ERROR: ffmpeg failed")
        assert evt is not None and evt["type"] == "error"


class TestChaptersAndLibrary:
    def test_chapters_endpoint_handles_empty_workdir(
        self, client: TestClient, uploaded_job: str = ""
    ):
        # Create a fresh job — no partN.flac files yet.
        with FIXTURE_EPUB.open("rb") as f:
            r = client.post(
                "/api/upload",
                files={"file": ("sample.epub", f, "application/epub+zip")},
            )
        job_id = r.json()["job_id"]

        r = client.get(f"/api/jobs/{job_id}/chapters")
        assert r.status_code == 200
        body = r.json()
        assert body["job_id"] == job_id
        assert body["completed"] == []

    def test_chapter_audio_404_when_missing(self, client: TestClient):
        with FIXTURE_EPUB.open("rb") as f:
            r = client.post(
                "/api/upload",
                files={"file": ("sample.epub", f, "application/epub+zip")},
            )
        job_id = r.json()["job_id"]
        assert client.get(f"/api/jobs/{job_id}/chapter/1/audio").status_code == 404

    def test_library_returns_list(self, client: TestClient):
        # Fresh test runs with no .m4b on disk produce an empty list, but the
        # endpoint must always return JSON shaped as a list.
        r = client.get("/api/library")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestSamples:
    def test_list_samples_initial(self, client: TestClient):
        r = client.get("/api/samples")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_upload_rejects_bad_extension(self, client: TestClient):
        r = client.post(
            "/api/samples",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 400

    def test_voice_test_rejects_empty_text(self, client: TestClient):
        r = client.post("/api/voice-test", json={"text": "   "})
        assert r.status_code == 400

    def test_voice_test_rejects_overlong_text(self, client: TestClient):
        r = client.post("/api/voice-test", json={"text": "x" * 2500})
        assert r.status_code == 400

    def test_voice_test_rejects_path_outside_samples(
        self, client: TestClient, tmp_path
    ):
        bogus = tmp_path / "evil.wav"
        bogus.write_bytes(b"\0\0\0\0")
        r = client.post(
            "/api/voice-test",
            json={"text": "hi there", "sample_path": str(bogus)},
        )
        assert r.status_code == 400
        assert "uploaded sample" in r.json()["detail"]

    def test_start_rejects_missing_output_dir(self, client: TestClient, tmp_path):
        # Upload + name first so a .txt exists.
        with FIXTURE_EPUB.open("rb") as f:
            r = client.post(
                "/api/upload",
                files={"file": ("sample.epub", f, "application/epub+zip")},
            )
        job_id = r.json()["job_id"]
        client.post(f"/api/jobs/{job_id}/naming", json={"method": "toc"})

        bogus = tmp_path / "does_not_exist"
        r = client.post(
            f"/api/jobs/{job_id}/start",
            json={"settings": {"output_dir": str(bogus)}},
        )
        assert r.status_code == 400
        assert "Output folder" in r.json()["detail"]

    def test_upload_and_round_trip_wav(self, client: TestClient, tmp_path):
        # Minimal 44-byte WAV header with no sample frames; enough to round-trip.
        wav_bytes = bytes.fromhex(
            "52494646" "24000000" "57415645"  # RIFF/size/WAVE
            "666d7420" "10000000" "01000100"  # fmt /size/PCM,1ch
            "44ac0000" "88580100" "02001000"  # 44100Hz/byterate/block,16bit
            "64617461" "00000000"             # data/0
        )
        r = client.post(
            "/api/samples",
            files={"file": ("smoke.wav", wav_bytes, "audio/wav")},
        )
        assert r.status_code == 200
        assert r.json()["filename"] == "smoke.wav"

        # Listing now contains it
        names = [e["filename"] for e in client.get("/api/samples").json()]
        assert "smoke.wav" in names

        # Round-trip download
        r = client.get("/api/samples/smoke.wav")
        assert r.status_code == 200
        assert r.content == wav_bytes
