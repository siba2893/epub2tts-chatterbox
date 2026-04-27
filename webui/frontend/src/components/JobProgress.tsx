import { useEffect, useRef, useState } from "react";
import {
  JobStatus,
  ProgressEvent,
  cancelJob,
  getJob,
  subscribeEvents,
} from "../api";

interface Props {
  jobId: string;
}

export default function JobProgress({ jobId }: Props) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [device, setDevice] = useState<string | null>(null);
  const logsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    getJob(jobId).then(setStatus).catch(() => undefined);
  }, [jobId]);

  useEffect(() => {
    const unsubscribe = subscribeEvents(jobId, (e: ProgressEvent) => {
      switch (e.type) {
        case "chapter":
          setStatus((s) =>
            s
              ? {
                  ...s,
                  current_chapter: e.index,
                  chapters_total: e.total,
                  state: "running",
                }
              : s
          );
          setLogs((l) => [...l, `chapter ${e.index}/${e.total}: ${e.title}`]);
          break;
        case "device":
          setDevice(e.device);
          break;
        case "skip_chapter":
        case "log":
          setLogs((l) => [...l, e.raw].slice(-200));
          break;
        case "error":
          setLogs((l) => [...l, "error: " + e.raw].slice(-200));
          break;
        case "state":
          setStatus((s) => (s ? { ...s, state: e.state } : s));
          break;
      }
    });

    const tick = setInterval(() => {
      getJob(jobId)
        .then(setStatus)
        .catch(() => undefined);
    }, 4000);

    return () => {
      unsubscribe();
      clearInterval(tick);
    };
  }, [jobId]);

  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs]);

  const ratio =
    status && status.chapters_total > 0
      ? Math.min(1, (status.current_chapter ?? 0) / status.chapters_total)
      : 0;

  return (
    <section className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-zinc-500">
            step 04
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">
            Converting
          </h2>
          {device && (
            <p className="mt-1 text-xs text-zinc-500">device: {device}</p>
          )}
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-widest text-zinc-500">
            state
          </div>
          <div className="mt-1 text-sm font-mono">
            {status?.state ?? "—"}
          </div>
        </div>
      </div>

      <div className="surface p-6 space-y-5">
        <div className="grid grid-cols-3 text-center">
          <Stat
            label="chapter"
            value={
              status
                ? `${status.current_chapter ?? 0}/${status.chapters_total || "?"}`
                : "—"
            }
          />
          <Stat
            label="elapsed"
            value={fmtSeconds(status?.elapsed_seconds)}
          />
          <Stat
            label="eta"
            value={
              status?.eta_seconds != null
                ? fmtSeconds(status.eta_seconds)
                : "—"
            }
          />
        </div>

        <div className="h-1.5 bg-zinc-900 rounded-full overflow-hidden">
          <div
            className="h-full bg-zinc-100 transition-all duration-700 ease-out"
            style={{ width: `${ratio * 100}%` }}
          />
        </div>
      </div>

      <div className="surface-muted">
        <div className="px-4 py-2 text-xs uppercase tracking-wider text-zinc-500 border-b border-zinc-800">
          log
        </div>
        <div
          ref={logsRef}
          className="px-4 py-3 max-h-72 overflow-auto font-mono text-xs leading-relaxed space-y-1"
        >
          {logs.length === 0 ? (
            <span className="text-zinc-600">no events yet…</span>
          ) : (
            logs.map((l, i) => (
              <div key={i} className="text-zinc-300 whitespace-pre-wrap">
                {l}
              </div>
            ))
          )}
        </div>
      </div>

      <div className="flex justify-end">
        <button
          className="btn"
          disabled={
            !status || ["done", "failed", "cancelled"].includes(status.state)
          }
          onClick={() => cancelJob(jobId).then(setStatus)}
        >
          cancel
        </button>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-widest text-zinc-500">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function fmtSeconds(s: number | null | undefined): string {
  if (s == null) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) {
    const m = Math.floor(s / 60);
    const r = Math.round(s % 60);
    return `${m}m ${r}s`;
  }
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}
