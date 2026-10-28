import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

// ── Types ─────────────────────────────────────────────────────────────────────

export interface CreateSessionPayload {
  query: string;
  paper_limit: number;
  relevance_threshold: number;
  offline_only: boolean;
  file_ids: string[];
}

export interface PipelineState {
  [stage: string]: {
    status: "pending" | "active" | "done" | "failed";
    papers_found?: number;
    papers_deduped?: number;
    papers_passed?: number;
    papers_processed?: number;
    error?: string;
  };
}

export interface Session {
  session_id: string;
  query: string;
  status: string;
  llm_fallback_used: boolean;
  paper_limit: number;
  relevance_threshold: number;
  pipeline_state: PipelineState;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface Paper {
  id: string;
  title: string;
  authors: string[];
  year: number | null;
  source: string;
  relevance_score: number | null;
  topic_categories: string[];
  abstract_summary: string | null;
  key_contributions: string[];
  limitations: string[];
  methodology: string | null;
  datasets: { name: string; size: string }[];
  metrics: { name: string; value: string }[];
  url: string | null;
  citation_apa: string | null;
  citation_ieee: string | null;
  citation_bibtex: string | null;
}

export interface Gap {
  gap_index: number;
  title: string;
  explanation: string;
  supporting_paper_ids: string[];
}

export interface Report {
  full_text: string;
  executive_summary: string | null;
  word_count: number;
  section_headings: string[];
}

export interface ComparisonRow {
  title: string;
  authors: string;
  year: number | null;
  methodology: string | null;
  datasets: string;
  metrics: string;
  relevance_score: number | null;
  key_contributions: string;
}

export interface SessionResults {
  session_id: string;
  query: string;
  papers: Paper[];
  gaps: Gap[];
  report: Report | null;
  comparison_table: ComparisonRow[];
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  year?: number | null;
  relevance_score?: number | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  weight: number;
}

export interface KnowledgeGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface UploadedFile {
  file_id: string;
  filename: string;
  size_bytes: number;
  status: string;
}

export interface UploadResponse {
  uploaded: UploadedFile[];
  rejected: { filename: string; reason: string }[];
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const createSession = (payload: CreateSessionPayload) =>
  api.post<Session>("/sessions", payload).then((r) => r.data);

export const getSession = (sessionId: string) =>
  api.get<Session>(`/sessions/${sessionId}`).then((r) => r.data);

export const listSessions = (page = 1, pageSize = 20, status?: string) =>
  api
    .get("/sessions", { params: { page, page_size: pageSize, status } })
    .then((r) => r.data);

export const getResults = (sessionId: string) =>
  api.get<SessionResults>(`/sessions/${sessionId}/results`).then((r) => r.data);

export const cancelSession = (sessionId: string) =>
  api.post(`/sessions/${sessionId}/cancel`).then((r) => r.data);

export const getGraph = (sessionId: string) =>
  api.get<KnowledgeGraph>(`/sessions/${sessionId}/graph`).then((r) => r.data);

export const uploadFiles = (files: File[]) => {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return api
    .post<UploadResponse>("/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
};

export const getExportUrl = (
  sessionId: string,
  format: "markdown" | "pdf" | "json",
  citationStyle = "apa"
) =>
  `${BASE_URL}/api/v1/sessions/${sessionId}/export?format=${format}&citation_style=${citationStyle}`;
