import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useRef } from "react";
import { Loader2, Download, AlertTriangle } from "lucide-react";
import { getGraph } from "../services/api";

// Lazy-load the heavy canvas-based graph library
const ForceGraph2D = lazy(() => import("react-force-graph-2d"));

const NODE_COLORS: Record<string, string> = {
  paper: "#3b63f7",
  topic: "#10b981",
  gap:   "#f59e0b",
};

const EDGE_COLORS: Record<string, string> = {
  paper_to_topic:           "#94a3b8",
  shared_gap:               "#f59e0b",
  methodological_similarity:"#a78bfa",
};

interface Props { sessionId: string; }

export default function KnowledgeGraphView({ sessionId }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["graph", sessionId],
    queryFn: () => getGraph(sessionId),
    staleTime: Infinity,
  });

  const graphRef = useRef<any>(null);

  const handleExport = () => {
    if (!data) return;
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `graph_${sessionId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="card p-12 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="card p-8 text-center text-slate-400">
        <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
        <p>Could not load knowledge graph.</p>
      </div>
    );
  }

  // Transform to react-force-graph format
  const graphData = {
    nodes: data.nodes.map((n) => ({
      id: n.id,
      label: n.label,
      type: n.type,
      color: NODE_COLORS[n.type] || "#94a3b8",
      val: n.type === "paper" ? 4 : n.type === "gap" ? 8 : 6,
    })),
    links: data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      type: e.type,
      color: EDGE_COLORS[e.type] || "#cbd5e1",
    })),
  };

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">Knowledge Graph</h2>
          <p className="text-xs text-slate-400">{data.nodes.length} nodes · {data.edges.length} edges</p>
        </div>
        {/* Legend */}
        <div className="flex items-center gap-4 text-xs text-slate-500">
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
              {type.charAt(0).toUpperCase() + type.slice(1)}
            </div>
          ))}
          <button onClick={handleExport} className="btn-secondary py-1 text-xs ml-2">
            <Download className="w-3.5 h-3.5" /> Export JSON
          </button>
        </div>
      </div>

      <div style={{ height: 520 }}>
        <Suspense fallback={<div className="flex items-center justify-center h-full"><Loader2 className="w-6 h-6 animate-spin text-brand-500" /></div>}>
        <ForceGraph2D
          ref={graphRef}
          graphData={graphData}
          nodeLabel={(node: any) => `${node.type}: ${node.label}`}
          nodeColor={(node: any) => node.color}
          nodeVal={(node: any) => node.val}
          linkColor={(link: any) => link.color}
          linkDirectionalParticles={1}
          linkDirectionalParticleWidth={1.5}
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            const label = node.label?.slice(0, 22) + (node.label?.length > 22 ? "…" : "");
            const fontSize = Math.max(10 / globalScale, 3);
            ctx.fillStyle = node.color;
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI);
            ctx.fill();
            if (globalScale > 0.6) {
              ctx.font = `${fontSize}px Inter, sans-serif`;
              ctx.fillStyle = "#1e293b";
              ctx.textAlign = "center";
              ctx.fillText(label, node.x, node.y + node.val + fontSize);
            }
          }}
          width={undefined}
          height={520}
          backgroundColor="#f8fafc"
        />
        </Suspense>
      </div>
    </div>
  );
}
