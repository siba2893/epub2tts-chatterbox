import { useEffect, useState } from "react";
import { LibraryEntry, listLibrary } from "../api";

function fmtDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function fmtBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export default function Library() {
  const [entries, setEntries] = useState<LibraryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listLibrary()
      .then(setEntries)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <section className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-widest text-zinc-500">
          library
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">
          Completed audiobooks
        </h2>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {entries === null ? (
        <p className="text-sm text-zinc-500">loading…</p>
      ) : entries.length === 0 ? (
        <div className="surface p-10 text-center text-sm text-zinc-500">
          no .m4b files yet — finish a conversion to populate the library.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {entries.map((e) => (
            <div key={e.filename} className="surface p-5 space-y-3">
              <div>
                <h3 className="text-base font-semibold tracking-tight">
                  {e.title || e.filename}
                </h3>
                {e.author && (
                  <p className="text-xs text-zinc-500 mt-0.5">{e.author}</p>
                )}
              </div>
              <div className="flex justify-between text-xs text-zinc-500 font-mono">
                <span>{fmtDuration(e.duration_seconds)}</span>
                <span>{fmtBytes(e.size_bytes)}</span>
              </div>
              <p className="text-[10px] text-zinc-600 font-mono break-all">
                {e.filename}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
