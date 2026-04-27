import { useRef, useState } from "react";
import { uploadEpub } from "../api";

interface Props {
  onUploaded: (jobId: string, meta: { title: string; author: string }) => void;
}

export default function UploadCard({ onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const res = await uploadEpub(file);
      onUploaded(res.job_id, { title: res.title, author: res.author });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="surface p-8 text-center space-y-4">
      <div>
        <p className="text-xs uppercase tracking-widest text-zinc-500">
          step 01
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">
          Pick an EPUB
        </h2>
        <p className="mt-2 text-sm text-zinc-400">
          The file is parsed locally and prepared for chapter naming.
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".epub,application/epub+zip"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFile(f);
        }}
      />

      <button
        className="btn-primary"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
      >
        {busy ? "uploading…" : "choose .epub file"}
      </button>

      {error && (
        <p className="text-xs text-red-400 mt-2">{error}</p>
      )}
    </section>
  );
}
