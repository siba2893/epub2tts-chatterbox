import { useEffect, useState } from "react";
import {
  ChapterListing,
  chapterAudioUrl,
  listChapters,
  rerunChapter,
} from "../api";

interface Props {
  jobId: string;
  /** If true, the list refreshes itself every 4 seconds (used during a run). */
  live?: boolean;
}

export default function ChapterList({ jobId, live = false }: Props) {
  const [data, setData] = useState<ChapterListing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<number | null>(null);

  function refresh() {
    listChapters(jobId)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }

  useEffect(() => {
    refresh();
    if (!live) return;
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, live]);

  async function rerun(n: number) {
    setPending(n);
    try {
      await rerunChapter(jobId, n);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(null);
    }
  }

  if (error) return <p className="text-xs text-red-400">{error}</p>;
  if (!data) return <p className="text-xs text-zinc-500">loading chapters…</p>;
  if (data.completed.length === 0)
    return (
      <p className="text-xs text-zinc-500 italic">
        no completed chapters on disk yet.
      </p>
    );

  return (
    <ul className="space-y-1">
      {data.completed.map((c) => (
        <li
          key={c.index}
          className="flex items-center gap-3 px-3 py-2 surface-muted text-xs"
        >
          <span className="font-mono text-zinc-500 w-10">
            {String(c.index).padStart(2, "0")}
          </span>
          <span className="flex-1 truncate text-zinc-300">{c.filename}</span>
          <audio
            src={chapterAudioUrl(jobId, c.index)}
            controls
            preload="none"
            className="h-6 max-w-[200px]"
          />
          <button
            className="btn-ghost text-[10px] uppercase tracking-wider"
            disabled={pending === c.index}
            onClick={() => rerun(c.index)}
          >
            {pending === c.index ? "queued…" : "re-render"}
          </button>
        </li>
      ))}
    </ul>
  );
}
