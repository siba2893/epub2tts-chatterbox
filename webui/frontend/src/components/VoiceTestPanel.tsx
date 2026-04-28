import { useState } from "react";
import { Settings, voiceTest } from "../api";

interface Props {
  samplePath: string | null;
  sampleFilename: string;
  /** Settings inherited from the editor so the test reflects the user's
   *  exaggeration / cfg_weight / language choices. */
  settings: Pick<Settings, "exaggeration" | "cfg_weight" | "language">;
  onClose: () => void;
}

const DEFAULT_TEXT =
  "The morning light spilled across the wooden floor in long golden ribbons, " +
  "slow and patient and warm. Somewhere outside, a single bird was rehearsing " +
  "the same three notes over and over.";

export default function VoiceTestPanel({
  samplePath,
  sampleFilename,
  settings,
  onClose,
}: Props) {
  const [text, setText] = useState(DEFAULT_TEXT);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  async function generate() {
    if (!text.trim()) {
      setError("Type a paragraph first.");
      return;
    }
    setBusy(true);
    setError(null);
    setAudioUrl(null);
    try {
      const res = await voiceTest({
        text,
        sample_path: samplePath ?? undefined,
        exaggeration: settings.exaggeration,
        cfg_weight: settings.cfg_weight,
        language: settings.language ?? "en",
      });
      // Cache-bust so the same URL (rare) doesn't replay the previous file.
      setAudioUrl(`${res.url}?t=${Date.now()}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="surface p-4 space-y-3 border-emerald-500/40">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-zinc-500">
            try voice
          </p>
          <p className="text-sm text-zinc-200">
            <span className="text-zinc-500">sample: </span>
            <span className="font-mono text-emerald-300">{sampleFilename}</span>
          </p>
        </div>
        <button className="btn-ghost text-xs" onClick={onClose}>
          close
        </button>
      </div>

      <textarea
        className="input font-mono text-xs leading-relaxed"
        rows={5}
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={2000}
        placeholder="Type the paragraph you want to hear in this voice…"
      />

      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] text-zinc-500">
          first run loads the model (≈30–90 s). subsequent tests are fast.
          uses the same exaggeration / cfg_weight / language as the main settings.
        </p>
        <button className="btn-primary" disabled={busy} onClick={generate}>
          {busy ? "generating…" : "generate"}
        </button>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {audioUrl && (
        <div className="pt-2 border-t border-zinc-800">
          <audio
            src={audioUrl}
            controls
            autoPlay
            preload="auto"
            className="w-full h-10"
          />
        </div>
      )}
    </div>
  );
}
