import { useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2, XCircle, Loader2, Clock, ChevronRight,
  Search, Tags, FileText, Wrench, Lightbulb, BookOpen, Quote, ArrowLeft
} from "lucide-react";
import { getSession, cancelSession } from "../services/api";

const STAGES = [
  { key: "search",    label: "Search",       icon: Search,       desc: "Discovering papers from arXiv & Semantic Scholar" },
  { key: "classify",  label: "Classify",     icon: Tags,         desc: "Scoring relevance and categorising papers" },
  { key: "summarize", label: "Summarize",    icon: FileText,     desc: "Generating structured paper summaries" },
  { key: "extract",   label: "Extract",      icon: Wrench,       desc: "Extracting methodology, datasets, and metrics" },
  { key: "gaps",      label: "Gap Discovery",icon: Lightbulb,    desc: "Identifying research gaps across the corpus" },
  { key: "synthesize",label: "Synthesize",   icon: BookOpen,     desc: "Composing the literature review narrative" },
  { key: "cite",      label: "Cite",         icon: Quote,        desc: "Formatting APA, IEEE, and BibTeX references" },
];

const TERMINAL = ["DONE", "FAILED", "CANCELLED"];

export default function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const toastRef = useRef<NodeJS.Timeout | null>(null);

  const { data: session, isLoading } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSession(sessionId!),
    refetchInterval: (data) =>
      data && TERMINAL.includes(data.status) ? false : 2000,
    enabled: !!sessionId,
  });

  useEffect(() => {
    if (session?.status === "DONE") {
      toastRef.current = setTimeout(() => {
        navigate(`/session/${sessionId}/results`);
      }, 1200);
    }
    return () => { if (toastRef.current) clearTimeout(toastRef.current); };
  }, [session?.status, sessionId, navigate]);

  const handleCancel = async () => {
    if (!sessionId) return;
    await cancelSession(sessionId);
    navigate("/");
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  const pipelineState = session?.pipeline_state || {};

  return (
    <div className="min-h-screen bg-slate-50 py-10 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Back */}
        <button onClick={() => navigate("/")} className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-6 transition-colors">
          <ArrowLeft className="w-4 h-4" /> New search
        </button>

        {/* Header */}
        <div className="card p-6 mb-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-lg font-bold text-slate-900 mb-1">Running Pipeline</h1>
              <p className="text-sm text-slate-500 line-clamp-2">"{session?.query}"</p>
            </div>
            <StatusBadge status={session?.status || "INIT"} />
          </div>

          {session?.llm_fallback_used && (
            <div className="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              ⚠ Using fallback LLM (Ollama). OpenAI was unavailable.
            </div>
          )}
        </div>

        {/* Pipeline tracker */}
        <div className="card divide-y divide-slate-100">
          {STAGES.map(({ key, label, icon: Icon, desc }) => {
            const stageState = pipelineState[key];
            const stageStatus = stageState?.status || "pending";

            return (
              <div key={key} className="flex items-start gap-4 p-4">
                {/* Icon */}
                <div className={`mt-0.5 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
                  ${stageStatus === "done" ? "bg-emerald-100 text-emerald-600"
                    : stageStatus === "active" ? "bg-brand-100 text-brand-600"
                    : stageStatus === "failed" ? "bg-red-100 text-red-500"
                    : "bg-slate-100 text-slate-400"}`}
                >
                  {stageStatus === "done" ? <CheckCircle2 className="w-4 h-4" />
                    : stageStatus === "active" ? <Loader2 className="w-4 h-4 animate-spin" />
                    : stageStatus === "failed" ? <XCircle className="w-4 h-4" />
                    : <Clock className="w-4 h-4" />}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Icon className="w-3.5 h-3.5 text-slate-400" />
                    <span className={`text-sm font-semibold ${stageStatus === "active" ? "text-brand-700" : "text-slate-700"}`}>
                      {label}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">{desc}</p>

                  {/* Stage counts */}
                  {stageStatus === "done" && stageState && (
                    <div className="mt-1 text-xs text-emerald-600 font-medium">
                      {stageState.papers_found !== undefined && `Found ${stageState.papers_found} papers`}
                      {stageState.papers_deduped !== undefined && `, ${stageState.papers_deduped} after dedup`}
                      {stageState.papers_passed !== undefined && ` · ${stageState.papers_passed} passed threshold`}
                      {stageState.papers_processed !== undefined && ` · ${stageState.papers_processed} processed`}
                    </div>
                  )}

                  {/* Error */}
                  {stageStatus === "failed" && stageState?.error && (
                    <p className="mt-1 text-xs text-red-500">{stageState.error}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Actions */}
        <div className="mt-6 flex gap-3">
          {session?.status === "DONE" && (
            <button
              onClick={() => navigate(`/session/${sessionId}/results`)}
              className="btn-primary"
            >
              View Results <ChevronRight className="w-4 h-4" />
            </button>
          )}

          {session && !TERMINAL.includes(session.status) && (
            <button onClick={handleCancel} className="btn-secondary text-red-600 border-red-200 hover:bg-red-50">
              Cancel Pipeline
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    INIT:      { label: "Initialising", cls: "bg-slate-100 text-slate-600" },
    SEARCH:    { label: "Searching",    cls: "bg-blue-100 text-blue-700" },
    CLASSIFY:  { label: "Classifying", cls: "bg-purple-100 text-purple-700" },
    SUMMARIZE: { label: "Summarising", cls: "bg-indigo-100 text-indigo-700" },
    EXTRACT:   { label: "Extracting",  cls: "bg-cyan-100 text-cyan-700" },
    GAPS:      { label: "Finding Gaps",cls: "bg-yellow-100 text-yellow-700" },
    SYNTHESIZE:{ label: "Synthesising",cls: "bg-orange-100 text-orange-700" },
    CITE:      { label: "Citing",      cls: "bg-pink-100 text-pink-700" },
    DONE:      { label: "Complete ✓",  cls: "bg-emerald-100 text-emerald-700" },
    FAILED:    { label: "Failed",      cls: "bg-red-100 text-red-700" },
    CANCELLED: { label: "Cancelled",   cls: "bg-slate-100 text-slate-500" },
  };
  const { label, cls } = map[status] || { label: status, cls: "bg-slate-100 text-slate-600" };
  return (
    <span className={`flex-shrink-0 text-xs font-semibold px-2.5 py-1 rounded-full ${cls}`}>
      {label}
    </span>
  );
}
