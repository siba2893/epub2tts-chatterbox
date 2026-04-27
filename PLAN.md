# Web UI Implementation Plan

Stack: **FastAPI** backend + **React** (Vite) frontend + **TailwindCSS**.
Aesthetic: monochromatic, minimalist (zinc palette, no chrome, generous whitespace, single accent for active state).
No drag-and-drop — file picker button only.

---

## Phase 0 — Scaffolding

- [x] Repo branch `improvements/harden-and-test` on fork (siba2893).
- [x] Draft `PLAN.md`.
- [x] Draft `.omc/prd.json` with refined acceptance criteria.
- [x] Create `webui/backend/` and `webui/frontend/` directories.
- [x] Add `.gitignore` entries for `node_modules/`, `dist/`, build artifacts.
- [x] Add FastAPI deps to `requirements-dev.txt`.
- [x] Scaffold Vite React+TS project under `webui/frontend/` (manual scaffold — `npx create-vite` fails on this MSYS/cmd.exe shell handoff; PowerShell tool used for install/build).
- [x] Install + configure Tailwind with monochrome palette (zinc-based, single zinc-100 accent).

## Phase 1 — Backend foundation

- [x] `webui/backend/app.py`: FastAPI instance, CORS for localhost:5173, 16 routes registered.
- [x] `webui/backend/jobs.py`: in-memory `JobRegistry`, per-job working dir under `webui/backend/jobs/<id>/`, subprocess orchestration in a daemon thread, SSE event broadcast queue.
- [x] `webui/backend/schemas.py`: Pydantic models — `UploadResponse`, `JobStatus`, `Settings`, `ChapterPreviewRow`, `TextDocument`, `LibraryEntry`, `ResumeState`.
- [x] `POST /api/upload` — accepts EPUB, parses metadata, returns `{job_id, title, author, chapter_count}`.
- [x] `GET /api/jobs/{id}` — current status snapshot (state, current chapter, elapsed, ETA).
- [x] `GET /api/jobs/{id}/events` — SSE stream with backlog replay for late subscribers.
- [x] `POST /api/jobs/{id}/cancel` — `Popen.terminate`; preserves `partN.flac`.
- [x] `POST /api/jobs/{id}/start` — launches the existing CLI as `python -m epub2tts_chatterbox.epub2tts_chatterbox` with all settings forwarded as flags.
- [x] `GET /api/jobs/{id}/resume-state` — counts `partN.flac` on disk.
- [x] Verified backend imports via `from webui.backend.app import app`; all routes register.

## Phase 2 — Frontend foundation

- [x] React app boots; `npm run build` produces a clean ~157 KB bundle (49.83 KB gzip).
- [x] `src/api.ts` — typed fetch wrappers for upload, naming, text round-trip, start/cancel, status, plus an `EventSource`-based SSE helper.
- [x] Global layout: zinc-950 bg, zinc-100 text, max-w-3xl content column, 1px zinc-900 borders.
- [x] Page shell with header (project name) + footer (GitHub link) + stage-driven main slot.
- [x] Reusable Tailwind component classes — `.surface`, `.surface-muted`, `.btn`, `.btn-primary`, `.btn-ghost`, `.input`, `.label`.

## Phase 3 — Tier 1 features

### 1. EPUB upload via file picker
- [x] `<UploadCard>`: hidden `<input type="file" accept=".epub">` + styled label button. POST `/api/upload`, advances stage on success, surfaces backend errors inline.

### 2. Chapter naming preview, click-column-header to select
- [x] `GET /api/jobs/{id}/naming-preview` returns up to 6 sample rows, all four method columns.
- [x] `<NamingPreview>` table: methods as clickable column headers, selected column visually inverted (zinc-100 fill + zinc-950 text). "Continue with <method>" button POSTs `/api/jobs/{id}/naming`.
- [x] Backend writes the .txt non-interactively via `export_epub(..., interactive=False, naming_method=method)`.

### 3. Live progress via SSE
- [x] `parse_progress_line()` turns CLI logger lines into structured events (`chapter`, `device`, `skip_chapter`, `error`, `log`).
- [x] `<JobProgress>` subscribes to `/events`, shows current chapter / elapsed / ETA, a thin progress bar, and a tail-following log pane. Cancel button calls `/cancel`.

### 4. Inline .txt editor with chapter visualization
- [x] `GET /api/jobs/{id}/text` parses with `get_book` and returns structured `{title, author, chapters: [{title, paragraphs}]}`. `PUT` reverses to the .txt format.
- [x] `<ChapterEditor>` two-pane layout: chapter list sidebar + main editing pane (title, author, chapter title, paragraph textarea). Add / move-up / move-down / delete chapter; "Save & Convert" button persists then starts the job.

## Phase 4 — Tier 2 features

- [x] **Settings panel**: collapsible inline panel inside `<ChapterEditor>`; persists to `localStorage` under `epub2tts:settings`; forwarded to backend as Settings on start.
- [x] **Resume detection backend** (`/resume-state`): scans for `partN.flac`. Returns counts and titles (titles will be wired once we track them per job).
- [x] **Cancel** wired in `<JobProgress>` and disabled in terminal states (`done`/`failed`/`cancelled`).
- [ ] **Voice sample picker UI** (`<SampleBrowser>`) — backend storage endpoint and UI not yet built. (Tier 2, deferred.)
- [ ] **Pause** — chatterbox-tts has no native pause; modeled today as "cancel and resume on restart". UI affordance still pending.

## Phase 5 — Tier 3 polish

- [x] **Library backend** (`GET /api/library`) — lists every `.m4b` produced under `webui/backend/jobs/<id>/`.
- [ ] **Library UI** (`<Library>` grid with cover art) — pending.
- [ ] **Per-chapter audio preview** — pending (would stream `partN.flac`).
- [ ] **Re-render single chapter** — pending (would delete one `partN.flac` and run a partial pipeline).

## Phase 6 — Quality gate

- [x] Backend pytest suite: `webui/backend/tests/test_api.py` — 12 tests covering health, upload happy + sad path, naming preview, naming choice, text round-trip, 404 on unknown job, and 6 progress-parser cases.
- [x] `npm run build` produces `dist/index.html` + `assets/index-*.css` + `assets/index-*.js`, all clean.
- [x] Existing 49 unit tests still pass (no regression).
- [ ] Vitest + React Testing Library smoke tests for components — pending.
- [x] README updated with web UI quickstart.

## Phase 7 — Commit & push

- [x] Commit Phase 0–3 + backend tests.
- [x] Push to `improvements/harden-and-test` on the fork.
- [ ] Follow-up commits for remaining Tier 2/3 UI components.
