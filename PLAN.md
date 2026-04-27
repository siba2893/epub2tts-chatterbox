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
- [x] Scaffold Vite React+TS project under `webui/frontend/`.
- [x] Install + configure Tailwind with monochrome palette.

## Phase 1 — Backend foundation

- [x] `webui/backend/app.py`: FastAPI instance, CORS for localhost:5173, all routes registered.
- [x] `webui/backend/jobs.py`: in-memory `JobRegistry`, per-job working dir, subprocess orchestration in a daemon thread, SSE event broadcast queue with backlog replay.
- [x] `webui/backend/schemas.py`: Pydantic models for every request/response.
- [x] `POST /api/upload` — multipart EPUB → `{job_id, title, author, chapter_count}`.
- [x] `GET /api/jobs/{id}` — current status snapshot.
- [x] `GET /api/jobs/{id}/events` — SSE stream.
- [x] `POST /api/jobs/{id}/cancel` — preserves resume state.
- [x] `POST /api/jobs/{id}/start` — launches CLI as subprocess with all settings as flags.
- [x] `GET /api/jobs/{id}/resume-state` — disk inspection of `partN.flac`.
- [x] Verified backend imports cleanly.

## Phase 2 — Frontend foundation

- [x] React app boots; `npm run build` produces a clean ~163 KB bundle (51 KB gzip).
- [x] `src/api.ts` — typed fetch wrappers + `EventSource`-based SSE helper.
- [x] Global layout: zinc-950 bg, zinc-100 text, max-w-3xl content column, 1px zinc-900 borders.
- [x] Page shell with header (project link + nav) + footer (GitHub link).
- [x] Reusable Tailwind component classes — `.surface`, `.surface-muted`, `.btn`, `.btn-primary`, `.btn-ghost`, `.input`, `.label`.

## Phase 3 — Tier 1 features

### 1. EPUB upload via file picker
- [x] `<UploadCard>`: hidden `<input type="file" accept=".epub">` + styled label button. POST `/api/upload`, advances stage on success, surfaces backend errors inline.

### 2. Chapter naming preview, click-column-header to select
- [x] `GET /api/jobs/{id}/naming-preview` returns up to 6 sample rows for all four method columns.
- [x] `<NamingPreview>` table: methods as clickable column headers, selected column visually inverted. "Continue with <method>" button POSTs `/api/jobs/{id}/naming`.
- [x] Backend writes the .txt non-interactively via `export_epub(..., interactive=False, naming_method=method)`.

### 3. Live progress via SSE
- [x] `parse_progress_line()` turns CLI logger lines into structured events.
- [x] `<JobProgress>` subscribes to `/events`, shows current chapter / elapsed / ETA, a thin progress bar, scrolling log pane, and the live chapter list with per-chapter audio + re-render.

### 4. Inline .txt editor with chapter visualization
- [x] `GET/PUT /api/jobs/{id}/text` round-trips structured text.
- [x] `<ChapterEditor>` two-pane layout with add/move/delete chapter; "Save & Convert" persists then starts the job.

## Phase 4 — Tier 2 features

- [x] **Settings panel**: collapsible inside `<ChapterEditor>`; persisted to `localStorage`; forwarded as Settings on start.
- [x] **Resume detection backend** (`/resume-state`): scans for `partN.flac`.
- [x] **Cancel** wired in `<JobProgress>`, disabled in terminal states.
- [x] **Voice sample picker UI** (`<SampleBrowser>`): file picker, list with `<audio controls>` preview, click-to-select, "clear" button. Backend endpoints: `POST/GET /api/samples`, `GET /api/samples/{name}`.

## Phase 5 — Tier 3 polish

- [x] **Library backend** (`GET /api/library`) — enriched with mutagen MP4 tags (title, author, duration).
- [x] **Library UI** (`<Library>`): grid of cards with title/author/duration/size, accessible from header nav.
- [x] **Per-chapter audio preview** (`GET /api/jobs/{id}/chapter/{n}/audio`, `GET /api/jobs/{id}/chapters`): `<ChapterList>` with inline `<audio controls>` per completed chapter, live-refreshing during runs.
- [x] **Re-render single chapter** (`POST /api/jobs/{id}/chapter/{n}/rerun`): deletes that `partN.flac` and restarts the job; resume logic skips already-completed chapters so only the deleted one re-renders.

## Phase 6 — Quality gate

- [x] Backend pytest: 18 tests covering health, upload, naming preview, naming choice, text round-trip, status, progress parsing (6 cases), chapters listing, library, sample upload/list/download.
- [x] Frontend Vitest: 5 component smoke tests across `<UploadCard>` and `<NamingPreview>`.
- [x] `npm run build` clean — 17.65 KB CSS, 163.27 KB JS (51 KB gzip).
- [x] Existing 49 unit tests still pass — full suite is now **67 pytest + 5 Vitest = 72 tests passing**.
- [x] README updated with web UI quickstart.

## Phase 7 — Commit & push

- [x] Phase 0–3 + backend tests committed (`ee5d4cd`).
- [x] Tier 2/3 polish + Vitest committed.
- [x] Branch on fork: `improvements/harden-and-test`.
