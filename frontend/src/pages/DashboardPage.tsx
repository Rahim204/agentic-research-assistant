import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import {
  FileDown, FileJson, FileType2, ArrowLeft, ChevronDown, ChevronUp,
  ExternalLink, Loader2, AlertTriangle, BarChart3, Network
} from "lucide-react";
import { getResults, getExportUrl, type Paper, type Gap } from "../services/api";
import KnowledgeGraphView from "../components/KnowledgeGraphView";

const CITATION_STYLES = ["apa", "ieee", "bibtex"] as const;
type CitationStyle = typeof CITATION_STYLES[number];

export default function DashboardPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["results", sessionId],
    queryFn: () => getResults(sessionId!),
    enabled: !!sessionId,
    staleTime: Infinity,
  });

  const [tab, setTab] = useState<"review" | "papers" | "gaps" | "graph">("review");
  const [citationStyle, setCitationStyle] = useState<CitationStyle>("apa");
  const [search, setSearch] = useState("");
  const [filterYear, setFilterYear] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [expandedPaperId, setExpandedPaperId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-3" />
          <p className="text-slate-600">Could not load results.</p>
          <button onClick={() => navigate("/")} className="btn-primary mt-4">Go Home</button>
        </div>
      </div>
    );
  }

  const allCategories = Array.from(
    new Set(data.papers.flatMap((p) => p.topic_categories))
  ).sort();

  const filteredPapers = data.papers.filter((p) => {
    const matchSearch = p.title.toLowerCase().includes(search.toLowerCase());
    const matchYear = filterYear ? String(p.year) === filterYear : true;
    const matchCat = filterCategory ? p.topic_categories.includes(filterCategory) : true;
    return matchSearch && matchYear && matchCat;
  });

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top bar */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <button onClick={() => navigate("/")} className="text-slate-400 hover:text-slate-600">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <h1 className="text-sm font-semibold text-slate-700 truncate">
              {data.query}
            </h1>
          </div>

          {/* Export controls */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <select
              value={citationStyle}
              onChange={(e) => setCitationStyle(e.target.value as CitationStyle)}
              className="input-field w-24 py-1.5 text-xs"
            >
              {CITATION_STYLES.map((s) => (
                <option key={s} value={s}>{s.toUpperCase()}</option>
              ))}
            </select>
            <a href={getExportUrl(sessionId!, "markdown", citationStyle)} download className="btn-secondary py-1.5 text-xs">
              <FileType2 className="w-3.5 h-3.5" /> MD
            </a>
            <a href={getExportUrl(sessionId!, "pdf", citationStyle)} download className="btn-secondary py-1.5 text-xs">
              <FileDown className="w-3.5 h-3.5" /> PDF
            </a>
            <a href={getExportUrl(sessionId!, "json", citationStyle)} download className="btn-secondary py-1.5 text-xs">
              <FileJson className="w-3.5 h-3.5" /> JSON
            </a>
          </div>
        </div>

        {/* Stats row */}
        <div className="max-w-6xl mx-auto px-4 pb-3 flex gap-6 text-xs text-slate-500">
          <span><strong className="text-slate-700">{data.papers.length}</strong> papers</span>
          <span><strong className="text-slate-700">{data.gaps.length}</strong> research gaps</span>
          {data.report && <span><strong className="text-slate-700">{data.report.word_count.toLocaleString()}</strong> words in review</span>}
        </div>

        {/* Tabs */}
        <div className="max-w-6xl mx-auto px-4 flex gap-0 border-t border-slate-100">
          {(["review", "papers", "gaps", "graph"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2.5 text-sm font-medium capitalize border-b-2 transition-colors
                ${tab === t ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700"}`}
            >
              {t === "graph" ? "Knowledge Graph" : t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </header>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        {/* ── Review ─────────────────────────────────────────────────────── */}
        {tab === "review" && (
          <div className="card p-8">
            {data.report?.executive_summary && (
              <div className="mb-6 p-4 bg-brand-50 border border-brand-200 rounded-lg">
                <h3 className="text-sm font-bold text-brand-800 mb-2">Executive Summary</h3>
                <p className="text-sm text-brand-700 leading-relaxed">{data.report.executive_summary}</p>
              </div>
            )}
            <div className="prose prose-slate max-w-none prose-headings:font-serif">
              <ReactMarkdown>{data.report?.full_text || "*No review generated yet.*"}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* ── Papers ─────────────────────────────────────────────────────── */}
        {tab === "papers" && (
          <div>
            {/* Filters */}
            <div className="flex gap-3 mb-4 flex-wrap">
              <input
                type="search"
                placeholder="Search papers…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input-field max-w-xs"
              />
              <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)} className="input-field w-44">
                <option value="">All categories</option>
                {allCategories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <input
                type="number"
                placeholder="Filter by year"
                value={filterYear}
                onChange={(e) => setFilterYear(e.target.value)}
                className="input-field w-32"
              />
            </div>

            <p className="text-xs text-slate-400 mb-3">{filteredPapers.length} of {data.papers.length} papers</p>

            <div className="space-y-3">
              {filteredPapers.map((paper) => (
                <PaperCard
                  key={paper.id}
                  paper={paper}
                  citationStyle={citationStyle}
                  expanded={expandedPaperId === paper.id}
                  onToggle={() => setExpandedPaperId(expandedPaperId === paper.id ? null : paper.id)}
                />
              ))}
            </div>
          </div>
        )}

        {/* ── Gaps ───────────────────────────────────────────────────────── */}
        {tab === "gaps" && (
          <div className="space-y-4">
            {data.gaps.length === 0 ? (
              <div className="card p-8 text-center text-slate-400">No research gaps identified.</div>
            ) : data.gaps.map((gap) => (
              <GapCard key={gap.gap_index} gap={gap} papers={data.papers} />
            ))}
          </div>
        )}

        {/* ── Graph ──────────────────────────────────────────────────────── */}
        {tab === "graph" && (
          <KnowledgeGraphView sessionId={sessionId!} />
        )}
      </main>
    </div>
  );
}

// ── PaperCard ─────────────────────────────────────────────────────────────────

function PaperCard({
  paper, citationStyle, expanded, onToggle,
}: {
  paper: Paper;
  citationStyle: CitationStyle;
  expanded: boolean;
  onToggle: () => void;
}) {
  const citation = paper[`citation_${citationStyle}` as keyof Paper] as string | null;

  return (
    <div className="card overflow-hidden">
      <button onClick={onToggle} className="w-full text-left p-4 hover:bg-slate-50 transition-colors">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              {paper.year && <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">{paper.year}</span>}
              <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">{paper.source}</span>
              {paper.topic_categories.slice(0, 2).map((c) => (
                <span key={c} className="text-xs bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full">{c}</span>
              ))}
            </div>
            <h3 className="text-sm font-semibold text-slate-800 line-clamp-2">{paper.title}</h3>
            <p className="text-xs text-slate-400 mt-0.5">{paper.authors.slice(0, 3).join(", ")}{paper.authors.length > 3 ? " et al." : ""}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {paper.relevance_score !== null && (
              <div className="text-right">
                <div className="text-xs font-semibold text-emerald-600">{(paper.relevance_score * 100).toFixed(0)}%</div>
                <div className="text-[10px] text-slate-400">relevance</div>
              </div>
            )}
            {expanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </div>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-slate-100 p-4 space-y-4 text-sm">
          {paper.abstract_summary && (
            <div>
              <h4 className="font-semibold text-slate-700 mb-1">Summary</h4>
              <p className="text-slate-600 leading-relaxed">{paper.abstract_summary}</p>
            </div>
          )}

          {paper.key_contributions.length > 0 && (
            <div>
              <h4 className="font-semibold text-slate-700 mb-1">Key Contributions</h4>
              <ul className="list-disc list-inside space-y-0.5 text-slate-600">
                {paper.key_contributions.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}

          {paper.methodology && (
            <div>
              <h4 className="font-semibold text-slate-700 mb-1">Methodology</h4>
              <p className="text-slate-600">{paper.methodology}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            {paper.datasets.length > 0 && (
              <div>
                <h4 className="font-semibold text-slate-700 mb-1">Datasets</h4>
                {paper.datasets.map((d, i) => (
                  <p key={i} className="text-xs text-slate-500">{d.name} {d.size !== "Not reported" ? `(${d.size})` : ""}</p>
                ))}
              </div>
            )}
            {paper.metrics.length > 0 && (
              <div>
                <h4 className="font-semibold text-slate-700 mb-1">Metrics</h4>
                {paper.metrics.map((m, i) => (
                  <p key={i} className="text-xs text-slate-500">{m.name}: {m.value}</p>
                ))}
              </div>
            )}
          </div>

          {citation && (
            <div className="bg-slate-50 rounded-lg p-3">
              <h4 className="font-semibold text-slate-700 mb-1 text-xs uppercase tracking-wide">Citation ({citationStyle.toUpperCase()})</h4>
              <p className="text-xs text-slate-600 font-mono leading-relaxed whitespace-pre-wrap">{citation}</p>
            </div>
          )}

          {paper.url && (
            <a href={paper.url} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-brand-600 hover:underline">
              View paper <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      )}
    </div>
  );
}

// ── GapCard ───────────────────────────────────────────────────────────────────

function GapCard({ gap, papers }: { gap: Gap; papers: Paper[] }) {
  const supportingPapers = papers.filter((p) => gap.supporting_paper_ids.includes(p.id));
  return (
    <div className="card p-5">
      <div className="flex items-start gap-3">
        <span className="flex-shrink-0 w-7 h-7 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center text-xs font-bold">
          {gap.gap_index}
        </span>
        <div>
          <h3 className="text-sm font-bold text-slate-800 mb-1">{gap.title}</h3>
          <p className="text-sm text-slate-600 leading-relaxed">{gap.explanation}</p>
          {supportingPapers.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {supportingPapers.map((p) => (
                <span key={p.id} className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full line-clamp-1 max-w-xs">
                  {p.title.slice(0, 40)}{p.title.length > 40 ? "…" : ""}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
