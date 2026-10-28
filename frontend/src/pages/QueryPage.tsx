import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import { FlaskConical, Upload, X, FileText, Loader2, BookOpen } from "lucide-react";
import { createSession, uploadFiles, type UploadedFile } from "../services/api";

const STAGE_LABELS = [
  "Search", "Classify", "Summarize", "Extract", "Gaps", "Synthesize", "Cite",
];

export default function QueryPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [paperLimit, setPaperLimit] = useState(50);
  const [threshold, setThreshold] = useState(0.3);
  const [offlineOnly, setOfflineOnly] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [uploadedFileIds, setUploadedFileIds] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const onDrop = useCallback((accepted: File[]) => {
    const pdfs = accepted.filter((f) => f.type === "application/pdf");
    const invalid = accepted.filter((f) => f.type !== "application/pdf");
    if (invalid.length) {
      setErrors((e) => ({ ...e, files: `${invalid.length} file(s) rejected — only PDFs accepted.` }));
    }
    setPendingFiles((prev) => [...prev, ...pdfs]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxSize: 50 * 1024 * 1024,
  });

  const removeFile = (i: number) => {
    setPendingFiles((prev) => prev.filter((_, idx) => idx !== i));
  };

  const validate = () => {
    const e: Record<string, string> = {};
    if (!query.trim()) e.query = "Please enter a research topic or question.";
    if (query.length > 2000) e.query = "Query must be 2000 characters or fewer.";
    return e;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setErrors({});

    setSubmitting(true);
    try {
      // Upload PDFs first
      let fileIds = uploadedFileIds;
      if (pendingFiles.length > 0) {
        setUploading(true);
        const uploadResp = await uploadFiles(pendingFiles);
        fileIds = uploadResp.uploaded.map((f) => f.file_id);
        setUploadedFileIds(fileIds);
        if (uploadResp.rejected.length) {
          setErrors((prev) => ({
            ...prev,
            files: uploadResp.rejected.map((r) => `${r.filename}: ${r.reason}`).join(" | "),
          }));
        }
        setUploading(false);
      }

      const session = await createSession({
        query: query.trim(),
        paper_limit: paperLimit,
        relevance_threshold: threshold,
        offline_only: offlineOnly,
        file_ids: fileIds,
      });

      navigate(`/session/${session.session_id}`);
    } catch (err: any) {
      setErrors({ submit: err?.response?.data?.detail || "Failed to start session. Please try again." });
    } finally {
      setSubmitting(false);
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-950 via-slate-900 to-slate-800 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-brand-500/20 border border-brand-400/30 mb-4">
            <BookOpen className="w-8 h-8 text-brand-300" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Agentic Research Assistant</h1>
          <p className="text-slate-400 text-sm">
            AI-powered literature mining, gap discovery, and knowledge synthesis
          </p>
        </div>

        {/* Pipeline preview */}
        <div className="flex items-center justify-center gap-1 mb-8">
          {STAGE_LABELS.map((label, i) => (
            <div key={label} className="flex items-center">
              <span className="text-xs text-slate-500 bg-slate-800/60 px-2 py-1 rounded-full border border-slate-700">
                {label}
              </span>
              {i < STAGE_LABELS.length - 1 && (
                <span className="text-slate-700 mx-0.5">›</span>
              )}
            </div>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="card p-6 space-y-6">
          {/* Query */}
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-1.5">
              Research Topic / Question
            </label>
            <div className="relative">
              <textarea
                className={`input-field min-h-[100px] resize-y ${errors.query ? "border-red-400 ring-red-300" : ""}`}
                placeholder="e.g. Large language models for code generation — a systematic review"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                maxLength={2000}
              />
              <span className={`absolute bottom-2 right-3 text-xs ${query.length > 1900 ? "text-orange-500" : "text-slate-400"}`}>
                {query.length}/2000
              </span>
            </div>
            {errors.query && <p className="mt-1 text-xs text-red-500">{errors.query}</p>}
          </div>

          {/* Controls */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                Max papers per source: <span className="text-brand-600">{paperLimit}</span>
              </label>
              <input
                type="range" min={5} max={200} step={5}
                value={paperLimit}
                onChange={(e) => setPaperLimit(Number(e.target.value))}
                className="w-full accent-brand-600"
              />
              <div className="flex justify-between text-xs text-slate-400 mt-0.5">
                <span>5</span><span>200</span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                Relevance threshold: <span className="text-brand-600">{threshold.toFixed(2)}</span>
              </label>
              <input
                type="range" min={0} max={1} step={0.05}
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-full accent-brand-600"
              />
              <div className="flex justify-between text-xs text-slate-400 mt-0.5">
                <span>0.00</span><span>1.00</span>
              </div>
            </div>
          </div>

          {/* Offline toggle */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setOfflineOnly(!offlineOnly)}
              className={`relative w-10 h-5 rounded-full transition-colors ${offlineOnly ? "bg-brand-600" : "bg-slate-300"}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${offlineOnly ? "translate-x-5" : ""}`} />
            </button>
            <span className="text-sm text-slate-600">
              Offline mode (uploaded PDFs only — skip external API search)
            </span>
          </div>

          {/* File upload */}
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-1.5">
              Upload Papers (optional, PDF only, max 50 MB each)
            </label>
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-5 text-center cursor-pointer transition-colors
                ${isDragActive ? "border-brand-400 bg-brand-50" : "border-slate-300 hover:border-brand-400 hover:bg-brand-50/50"}`}
            >
              <input {...getInputProps()} />
              <Upload className="w-6 h-6 text-slate-400 mx-auto mb-2" />
              <p className="text-sm text-slate-500">
                {isDragActive ? "Drop PDFs here…" : "Drag & drop PDFs, or click to browse"}
              </p>
            </div>

            {errors.files && <p className="mt-1 text-xs text-red-500">{errors.files}</p>}

            {pendingFiles.length > 0 && (
              <ul className="mt-3 space-y-1">
                {pendingFiles.map((f, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm text-slate-600 bg-slate-50 rounded-lg px-3 py-1.5">
                    <FileText className="w-4 h-4 text-brand-500 flex-shrink-0" />
                    <span className="flex-1 truncate">{f.name}</span>
                    <span className="text-xs text-slate-400">{(f.size / 1024 / 1024).toFixed(1)} MB</span>
                    <button type="button" onClick={() => removeFile(i)} className="text-slate-400 hover:text-red-500">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {errors.submit && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {errors.submit}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || uploading}
            className="btn-primary w-full justify-center py-3 text-base"
          >
            {submitting || uploading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> {uploading ? "Uploading files…" : "Starting pipeline…"}</>
            ) : (
              <><FlaskConical className="w-4 h-4" /> Start Research Pipeline</>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
