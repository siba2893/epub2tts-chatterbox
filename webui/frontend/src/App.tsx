import { useState } from "react";
import UploadCard from "./components/UploadCard";
import NamingPreview from "./components/NamingPreview";
import ChapterEditor from "./components/ChapterEditor";
import JobProgress from "./components/JobProgress";
import Library from "./components/Library";

type Stage = "upload" | "naming" | "editing" | "running" | "library";

export default function App() {
  const [stage, setStage] = useState<Stage>("upload");
  const [jobId, setJobId] = useState<string | null>(null);
  const [meta, setMeta] = useState<{ title: string; author: string } | null>(null);

  return (
    <div className="min-h-full flex flex-col">
      <header className="border-b border-zinc-900">
        <div className="max-w-3xl mx-auto px-6 py-5 flex items-baseline justify-between">
          <button
            className="text-lg font-semibold tracking-tight hover:text-white"
            onClick={() => {
              setStage("upload");
              setJobId(null);
              setMeta(null);
            }}
          >
            epub2tts-chatterbox
          </button>
          <nav className="flex gap-5 text-xs uppercase tracking-widest">
            <button
              className={
                stage !== "library"
                  ? "text-zinc-200"
                  : "text-zinc-500 hover:text-zinc-300"
              }
              onClick={() => setStage("upload")}
            >
              convert
            </button>
            <button
              className={
                stage === "library"
                  ? "text-zinc-200"
                  : "text-zinc-500 hover:text-zinc-300"
              }
              onClick={() => setStage("library")}
            >
              library
            </button>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-3xl mx-auto px-6 py-10 space-y-8">
          {stage === "upload" && (
            <UploadCard
              onUploaded={(id, m) => {
                setJobId(id);
                setMeta(m);
                setStage("naming");
              }}
            />
          )}
          {stage === "naming" && jobId && (
            <NamingPreview
              jobId={jobId}
              onChosen={() => setStage("editing")}
              meta={meta}
            />
          )}
          {stage === "editing" && jobId && (
            <ChapterEditor
              jobId={jobId}
              onStarted={() => setStage("running")}
            />
          )}
          {stage === "running" && jobId && <JobProgress jobId={jobId} />}
          {stage === "library" && <Library />}
        </div>
      </main>

      <footer className="border-t border-zinc-900">
        <div className="max-w-3xl mx-auto px-6 py-4 text-xs text-zinc-500 flex justify-between">
          <span>monochromatic ui</span>
          <a
            href="https://github.com/siba2893/epub2tts-chatterbox"
            target="_blank"
            rel="noreferrer"
            className="hover:text-zinc-300"
          >
            github
          </a>
        </div>
      </footer>
    </div>
  );
}
