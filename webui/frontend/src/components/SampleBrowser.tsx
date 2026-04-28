import { useEffect, useRef, useState } from "react";
import { VoiceSample, deleteSample, listSamples, uploadSample } from "../api";

interface Props {
  selected: string | null;
  onSelect: (path: string | null) => void;
}

export default function SampleBrowser({ selected, onSelect }: Props) {
  const [samples, setSamples] = useState<VoiceSample[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  function refresh() {
    listSamples()
      .then(setSamples)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }
  useEffect(refresh, []);

  async function handleUpload(file: File) {
    setBusy(true);
    setError(null);
    try {
      await uploadSample(file);
      // Auto-select the new sample so users don't have to remember
      // a separate "click filename to select" step.
      const fresh = await listSamples();
      setSamples(fresh);
      const justUploaded = fresh.find((s) => s.filename === file.name);
      if (justUploaded) onSelect(justUploaded.path);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(s: VoiceSample) {
    if (!window.confirm(`Delete "${s.filename}"?`)) return;
    try {
      await deleteSample(s.filename);
      if (selected === s.path) onSelect(null);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const selectedSample = samples.find((s) => s.path === selected);
  return (
    <div className="surface-muted p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="label !mb-0">voice sample</span>
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="file"
            accept=".wav,.mp3,.flac,audio/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleUpload(f);
            }}
          />
          <button
            className="btn-ghost text-xs"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            {busy ? "uploading…" : "+ upload"}
          </button>
          <button
            className="btn-ghost text-xs"
            onClick={() => onSelect(null)}
            disabled={selected === null}
          >
            clear
          </button>
        </div>
      </div>

      <div className="text-xs">
        {selectedSample ? (
          <span className="text-zinc-300">
            <span className="text-zinc-500">selected: </span>
            <span className="font-mono text-emerald-300">
              {selectedSample.filename}
            </span>
          </span>
        ) : samples.length > 0 ? (
          <span className="text-amber-300">
            no sample selected — the model will use its default voice. click a
            row below to pick one.
          </span>
        ) : (
          <span className="text-zinc-500">no sample selected</span>
        )}
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {samples.length === 0 ? (
        <p className="text-xs text-zinc-500 italic">
          no samples yet — upload a 30–60 second clean voice clip.
        </p>
      ) : (
        <ul className="space-y-1">
          {samples.map((s) => {
            const active = selected === s.path;
            return (
              <li
                key={s.filename}
                className={`flex items-center gap-3 px-2 py-1.5 rounded transition-colors border ${
                  active
                    ? "bg-zinc-100 text-zinc-950 border-emerald-400"
                    : "hover:bg-zinc-800 border-transparent"
                }`}
              >
                <span className="w-4 text-emerald-500 text-sm flex-shrink-0">
                  {active ? "✓" : ""}
                </span>
                <button
                  className={`text-left text-xs flex-1 truncate ${
                    active ? "" : "text-zinc-200"
                  }`}
                  onClick={() => onSelect(s.path)}
                  title={s.path}
                >
                  {s.filename}
                </button>
                <audio
                  src={s.url}
                  controls
                  preload="none"
                  className="h-6 max-w-[180px]"
                />
                <button
                  className={`text-[10px] uppercase tracking-wider px-2 py-1 rounded transition-colors ${
                    active
                      ? "text-zinc-700 hover:text-red-600"
                      : "text-zinc-500 hover:text-red-400"
                  }`}
                  onClick={() => handleDelete(s)}
                  title={`delete ${s.filename}`}
                >
                  ✕
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
