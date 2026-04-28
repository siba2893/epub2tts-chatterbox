// Typed API client for the FastAPI backend.

export type JobState =
  | "queued"
  | "uploaded"
  | "naming"
  | "editing"
  | "running"
  | "paused"
  | "done"
  | "failed"
  | "cancelled";

export interface UploadResponse {
  job_id: string;
  title: string;
  author: string;
  chapter_count: number;
}

export interface ChapterPreviewRow {
  toc: string | null;
  heading: string | null;
  class: string | null;
  fallback: string | null;
}

export interface ChapterPreviewResponse {
  rows: ChapterPreviewRow[];
}

export interface ChapterEdit {
  title: string;
  paragraphs: string[];
}

export interface TextDocument {
  title: string;
  author: string;
  chapters: ChapterEdit[];
}

export type TTSEngine = "chatterbox" | "xtts_v2";

export interface Settings {
  engine: TTSEngine;
  paragraph_pause_ms: number;
  min_sentence_words: number;
  exaggeration: number;
  cfg_weight: number;
  retry_count: number;
  sample_path?: string | null;
  cover_path?: string | null;
  notitles?: boolean;
  language?: string;
  output_dir?: string | null;
}

export interface JobStatus {
  job_id: string;
  state: JobState;
  title: string | null;
  author: string | null;
  error: string | null;
  chapters_total: number;
  chapters_done: number;
  current_chapter: number | null;
  current_paragraph: number | null;
  elapsed_seconds: number;
  eta_seconds: number | null;
}

const API = ""; // empty = same-origin via Vite proxy

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) msg = body.detail;
    } catch {
      /* swallow */
    }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

export async function uploadEpub(file: File): Promise<UploadResponse> {
  const fd = new FormData();
  fd.append("file", file);
  return json(await fetch(`${API}/api/upload`, { method: "POST", body: fd }));
}

export async function getNamingPreview(
  jobId: string
): Promise<ChapterPreviewResponse> {
  return json(await fetch(`${API}/api/jobs/${jobId}/naming-preview`));
}

export async function chooseNaming(
  jobId: string,
  method: "auto" | "toc" | "heading" | "class" | "fallback"
): Promise<{ job_id: string; method: string }> {
  return json(
    await fetch(`${API}/api/jobs/${jobId}/naming`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ method }),
    })
  );
}

export async function getText(jobId: string): Promise<TextDocument> {
  return json(await fetch(`${API}/api/jobs/${jobId}/text`));
}

export async function putText(
  jobId: string,
  doc: TextDocument
): Promise<TextDocument> {
  return json(
    await fetch(`${API}/api/jobs/${jobId}/text`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(doc),
    })
  );
}

export async function startJob(
  jobId: string,
  settings: Settings
): Promise<JobStatus> {
  return json(
    await fetch(`${API}/api/jobs/${jobId}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    })
  );
}

export async function cancelJob(jobId: string): Promise<JobStatus> {
  return json(
    await fetch(`${API}/api/jobs/${jobId}/cancel`, { method: "POST" })
  );
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return json(await fetch(`${API}/api/jobs/${jobId}`));
}

export type ProgressEvent =
  | { type: "state"; state: JobState; error?: string; exit_code?: number }
  | { type: "chapter"; index: number; total: number; title: string }
  | { type: "skip_chapter"; raw: string }
  | { type: "device"; device: string }
  | { type: "log"; raw: string }
  | { type: "error"; raw: string };

// ---------------------------------------------------------------------------
// Voice samples
// ---------------------------------------------------------------------------

export interface VoiceSample {
  filename: string;
  size_bytes: number;
  url: string;
  path: string;
}

export async function listSamples(): Promise<VoiceSample[]> {
  return json(await fetch(`${API}/api/samples`));
}

export async function uploadSample(
  file: File
): Promise<{ filename: string; size_bytes: number }> {
  const fd = new FormData();
  fd.append("file", file);
  return json(await fetch(`${API}/api/samples`, { method: "POST", body: fd }));
}

export async function deleteSample(name: string): Promise<{ deleted: string }> {
  return json(
    await fetch(`${API}/api/samples/${encodeURIComponent(name)}`, {
      method: "DELETE",
    })
  );
}

export interface VoiceTestResult {
  filename: string;
  url: string;
  size_bytes: number;
}

export async function voiceTest(input: {
  text: string;
  sample_path?: string | null;
  exaggeration?: number;
  cfg_weight?: number;
  language?: string;
  engine?: TTSEngine;
}): Promise<VoiceTestResult> {
  return json(
    await fetch(`${API}/api/voice-test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  );
}

// ---------------------------------------------------------------------------
// Library + per-chapter
// ---------------------------------------------------------------------------

export interface LibraryEntry {
  filename: string;
  title: string | null;
  author: string | null;
  cover_url: string | null;
  duration_seconds: number | null;
  size_bytes: number;
}

export async function listLibrary(): Promise<LibraryEntry[]> {
  return json(await fetch(`${API}/api/library`));
}

export interface ChapterFile {
  index: number;
  size_bytes: number;
  filename: string;
}

export interface ChapterListing {
  job_id: string;
  completed: ChapterFile[];
  total: number;
}

export async function listChapters(jobId: string): Promise<ChapterListing> {
  return json(await fetch(`${API}/api/jobs/${jobId}/chapters`));
}

export function chapterAudioUrl(jobId: string, n: number): string {
  return `${API}/api/jobs/${jobId}/chapter/${n}/audio`;
}

export async function rerunChapter(
  jobId: string,
  n: number
): Promise<JobStatus> {
  return json(
    await fetch(`${API}/api/jobs/${jobId}/chapter/${n}/rerun`, {
      method: "POST",
    })
  );
}

export function subscribeEvents(
  jobId: string,
  onEvent: (e: ProgressEvent) => void
): () => void {
  const es = new EventSource(`${API}/api/jobs/${jobId}/events`);
  es.onmessage = (msg) => {
    if (!msg.data) return;
    try {
      onEvent(JSON.parse(msg.data) as ProgressEvent);
    } catch {
      /* malformed */
    }
  };
  es.onerror = () => {
    // EventSource auto-reconnects; surface a state event for UI feedback.
    onEvent({ type: "state", state: "running" });
  };
  return () => es.close();
}
