import { useEffect, useState } from "react";
import {
  ChapterPreviewRow,
  chooseNaming,
  getNamingPreview,
} from "../api";

type Method = "toc" | "heading" | "class" | "fallback";
const METHODS: Method[] = ["toc", "heading", "class", "fallback"];

interface Props {
  jobId: string;
  meta: { title: string; author: string } | null;
  onChosen: () => void;
}

export default function NamingPreview({ jobId, meta, onChosen }: Props) {
  const [rows, setRows] = useState<ChapterPreviewRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<Method>("toc");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getNamingPreview(jobId)
      .then((r) => setRows(r.rows))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [jobId]);

  async function continueWith() {
    setSubmitting(true);
    try {
      await chooseNaming(jobId, picked);
      onChosen();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-widest text-zinc-500">
          step 02
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">
          Pick a chapter naming method
        </h2>
        {meta && (
          <p className="mt-1 text-sm text-zinc-400">
            <span className="text-zinc-200">{meta.title}</span>{" "}
            <span className="text-zinc-500">by {meta.author}</span>
          </p>
        )}
        <p className="mt-2 text-sm text-zinc-400">
          Click a column header to select that method.
        </p>
      </div>

      <div className="surface overflow-hidden">
        {error && (
          <div className="p-4 text-xs text-red-400 border-b border-zinc-800">
            {error}
          </div>
        )}
        <table className="w-full text-sm">
          <thead className="bg-zinc-900/60">
            <tr>
              <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-zinc-500 w-10">
                #
              </th>
              {METHODS.map((m) => {
                const active = picked === m;
                return (
                  <th
                    key={m}
                    onClick={() => setPicked(m)}
                    className={`px-3 py-2 text-left text-xs uppercase tracking-wider cursor-pointer transition-colors select-none ${
                      active
                        ? "bg-zinc-100 text-zinc-950"
                        : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
                    }`}
                  >
                    {m}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows === null ? (
              <tr>
                <td colSpan={5} className="p-6 text-center text-zinc-500">
                  loading preview…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-6 text-center text-zinc-500">
                  no sample chapters available
                </td>
              </tr>
            ) : (
              rows.map((row, i) => (
                <tr
                  key={i}
                  className="border-t border-zinc-900 hover:bg-zinc-900/40"
                >
                  <td className="px-3 py-2 text-zinc-500 font-mono text-xs">
                    {i + 1}
                  </td>
                  {METHODS.map((m) => {
                    const v =
                      m === "class"
                        ? (row.class as string | null)
                        : (row[m] as string | null);
                    return (
                      <td
                        key={m}
                        className={`px-3 py-2 ${
                          picked === m ? "text-zinc-100" : "text-zinc-300"
                        }`}
                      >
                        {v ?? <span className="text-zinc-600">—</span>}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex justify-end gap-3">
        <button
          className="btn-primary"
          disabled={submitting || !rows}
          onClick={continueWith}
        >
          {submitting ? "applying…" : "continue with " + picked}
        </button>
      </div>
    </section>
  );
}
