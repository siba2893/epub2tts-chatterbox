import { useEffect, useState } from "react";
import {
  ChapterEdit,
  Settings,
  TextDocument,
  getText,
  putText,
  startJob,
} from "../api";
import SampleBrowser from "./SampleBrowser";

interface Props {
  jobId: string;
  onStarted: () => void;
}

const DEFAULT_SETTINGS: Settings = {
  paragraph_pause_ms: 600,
  min_sentence_words: 8,
  exaggeration: 0.7,
  cfg_weight: 0.4,
  retry_count: 3,
  language: "en",
  notitles: false,
};

function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem("epub2tts:settings");
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    /* ignore */
  }
  return DEFAULT_SETTINGS;
}
function saveSettings(s: Settings) {
  localStorage.setItem("epub2tts:settings", JSON.stringify(s));
}

export default function ChapterEditor({ jobId, onStarted }: Props) {
  const [doc, setDoc] = useState<TextDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState<Settings>(loadSettings());
  const [showSettings, setShowSettings] = useState(true);

  useEffect(() => {
    getText(jobId)
      .then(setDoc)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [jobId]);

  function update(d: TextDocument) {
    setDoc({ ...d });
  }
  function updateChapter(i: number, c: ChapterEdit) {
    if (!doc) return;
    const chapters = doc.chapters.slice();
    chapters[i] = c;
    update({ ...doc, chapters });
  }
  function addChapter() {
    if (!doc) return;
    const chapters = doc.chapters.slice();
    chapters.push({ title: "New Chapter", paragraphs: [""] });
    update({ ...doc, chapters });
    setActive(chapters.length - 1);
  }
  function deleteChapter(i: number) {
    if (!doc) return;
    const chapters = doc.chapters.slice();
    chapters.splice(i, 1);
    update({ ...doc, chapters });
    setActive(Math.max(0, i - 1));
  }
  function move(i: number, delta: -1 | 1) {
    if (!doc) return;
    const j = i + delta;
    if (j < 0 || j >= doc.chapters.length) return;
    const chapters = doc.chapters.slice();
    [chapters[i], chapters[j]] = [chapters[j], chapters[i]];
    update({ ...doc, chapters });
    setActive(j);
  }

  async function saveAndStart() {
    if (!doc) return;
    setBusy(true);
    setError(null);
    try {
      await putText(jobId, doc);
      saveSettings(settings);
      await startJob(jobId, settings);
      onStarted();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <p className="text-sm text-red-400">{error}</p>;
  if (!doc) return <p className="text-sm text-zinc-500">loading text…</p>;
  const chapter = doc.chapters[active];

  return (
    <section className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-zinc-500">
            step 03
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">
            Review and edit chapters
          </h2>
        </div>
        <button
          className="btn-ghost text-xs"
          onClick={() => setShowSettings((v) => !v)}
        >
          {showSettings ? "hide settings" : "settings"}
        </button>
      </div>

      <div className="grid grid-cols-12 gap-4 min-h-[60vh]">
        <aside className="col-span-4 surface-muted p-2 overflow-auto max-h-[60vh]">
          <ul className="space-y-px text-sm">
            {doc.chapters.map((c, i) => (
              <li key={i}>
                <button
                  className={`w-full text-left px-3 py-2 rounded transition-colors ${
                    i === active
                      ? "bg-zinc-100 text-zinc-950"
                      : "hover:bg-zinc-800 text-zinc-300"
                  }`}
                  onClick={() => setActive(i)}
                >
                  <span className="font-mono text-xs text-zinc-500 mr-2">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  {c.title || "(untitled)"}
                </button>
              </li>
            ))}
          </ul>
          <button className="btn-ghost mt-2 w-full text-xs" onClick={addChapter}>
            + add chapter
          </button>
        </aside>

        <div className="col-span-8 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">title</label>
              <input
                className="input"
                value={doc.title}
                onChange={(e) => update({ ...doc, title: e.target.value })}
              />
            </div>
            <div>
              <label className="label">author</label>
              <input
                className="input"
                value={doc.author}
                onChange={(e) => update({ ...doc, author: e.target.value })}
              />
            </div>
          </div>

          <div>
            <label className="label">chapter title</label>
            <input
              className="input"
              value={chapter.title}
              onChange={(e) =>
                updateChapter(active, { ...chapter, title: e.target.value })
              }
            />
          </div>

          <div>
            <label className="label">paragraphs</label>
            <textarea
              className="input font-mono text-xs leading-relaxed"
              rows={14}
              value={chapter.paragraphs.join("\n\n")}
              onChange={(e) =>
                updateChapter(active, {
                  ...chapter,
                  paragraphs: e.target.value
                    .split(/\n\s*\n/)
                    .map((p) => p.trim())
                    .filter(Boolean),
                })
              }
            />
          </div>

          <div className="flex justify-between text-xs">
            <div className="flex gap-2">
              <button
                className="btn-ghost"
                onClick={() => move(active, -1)}
                disabled={active === 0}
              >
                ↑ move up
              </button>
              <button
                className="btn-ghost"
                onClick={() => move(active, 1)}
                disabled={active === doc.chapters.length - 1}
              >
                ↓ move down
              </button>
              <button
                className="btn-ghost text-red-400 hover:text-red-300"
                onClick={() => deleteChapter(active)}
              >
                delete
              </button>
            </div>
          </div>
        </div>
      </div>

      <SampleBrowser
        selected={settings.sample_path ?? null}
        onSelect={(p) => setSettings({ ...settings, sample_path: p })}
        testSettings={{
          exaggeration: settings.exaggeration,
          cfg_weight: settings.cfg_weight,
          language: settings.language,
        }}
      />

      {showSettings && (
        <SettingsPanel value={settings} onChange={setSettings} />
      )}

      <div className="flex justify-end">
        <button
          className="btn-primary"
          disabled={busy}
          onClick={saveAndStart}
        >
          {busy ? "starting…" : "save & convert"}
        </button>
      </div>
    </section>
  );
}

function SettingsPanel({
  value,
  onChange,
}: {
  value: Settings;
  onChange: (s: Settings) => void;
}) {
  function set<K extends keyof Settings>(key: K, v: Settings[K]) {
    onChange({ ...value, [key]: v });
  }
  return (
    <div className="surface-muted p-4 grid grid-cols-2 gap-4 text-sm">
      <div>
        <label className="label">paragraph pause (ms)</label>
        <input
          className="input"
          type="number"
          value={value.paragraph_pause_ms}
          onChange={(e) => set("paragraph_pause_ms", Number(e.target.value))}
        />
      </div>
      <div>
        <label className="label">min sentence words</label>
        <input
          className="input"
          type="number"
          value={value.min_sentence_words}
          onChange={(e) => set("min_sentence_words", Number(e.target.value))}
        />
      </div>
      <div>
        <label className="label">exaggeration</label>
        <input
          className="input"
          type="number"
          step={0.05}
          value={value.exaggeration}
          onChange={(e) => set("exaggeration", Number(e.target.value))}
        />
      </div>
      <div>
        <label className="label">cfg weight</label>
        <input
          className="input"
          type="number"
          step={0.05}
          value={value.cfg_weight}
          onChange={(e) => set("cfg_weight", Number(e.target.value))}
        />
      </div>
      <div>
        <label className="label">retry count</label>
        <input
          className="input"
          type="number"
          value={value.retry_count}
          onChange={(e) => set("retry_count", Number(e.target.value))}
        />
      </div>
      <div>
        <label className="label">language</label>
        <input
          className="input"
          value={value.language ?? "en"}
          onChange={(e) => set("language", e.target.value)}
        />
      </div>
      <div className="col-span-2">
        <label className="label">
          output folder{" "}
          <span className="text-zinc-600 normal-case tracking-normal">
            — absolute path on this machine; M4B will be copied here after
            conversion. leave empty to keep it in the job workdir.
          </span>
        </label>
        <input
          className="input font-mono text-xs"
          placeholder="C:\Users\you\Audiobooks   or   /home/you/Audiobooks"
          value={value.output_dir ?? ""}
          onChange={(e) =>
            set("output_dir", e.target.value.trim() ? e.target.value : null)
          }
        />
      </div>
      <div className="col-span-2 flex items-center gap-2 pt-2">
        <input
          id="notitles"
          type="checkbox"
          checked={value.notitles ?? false}
          onChange={(e) => set("notitles", e.target.checked)}
          className="h-4 w-4 rounded border-zinc-700 bg-zinc-950"
        />
        <label htmlFor="notitles" className="text-xs text-zinc-300 cursor-pointer">
          skip reading chapter titles aloud (<span className="font-mono">--notitles</span>)
        </label>
      </div>
    </div>
  );
}
