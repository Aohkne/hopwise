import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d";
import type { TraceStep } from "../../api/client";

interface TNode {
  id: string;
  label: string;
  caption: string;
  order: number;
  x?: number;
  y?: number;
}

interface TLink {
  source: string | TNode;
  target: string | TNode;
  kind: string;
}

interface Props {
  steps: TraceStep[];
  answerNodeId: string | null;
  selectedId: string | null;
  onSelect: (nodeId: string) => void;
}

/** Graph các node model đã đi qua, theo thứ tự bước (số trên node). */
export function TraceGraph({ steps, answerNodeId, selectedId, onSelect }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<ForceGraphMethods<TNode, TLink> | undefined>(undefined);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const data = useMemo(() => {
    const nodes = new Map<string, TNode>();
    const links: TLink[] = [];
    for (const s of steps) {
      if (s.phase !== "visit" || !s.node_id) continue;
      if (!nodes.has(s.node_id)) {
        nodes.set(s.node_id, {
          id: s.node_id,
          label: s.node_label ?? "?",
          caption: s.node_caption ?? s.node_id,
          order: nodes.size + 1,
        });
      }
      if (s.from_node_id && s.via_edge && s.via_edge !== "backtrack" && nodes.has(s.from_node_id)) {
        links.push({ source: s.from_node_id, target: s.node_id, kind: s.via_edge });
      }
    }
    return { nodes: [...nodes.values()], links };
  }, [steps]);

  return (
    <div ref={wrapRef} className="relative h-full min-h-[260px] w-full bg-white">
      {data.nodes.length === 0 && (
        <p className="absolute inset-0 flex items-center justify-center text-[11px] text-neutral-400">
          chưa đi tới node nào
        </p>
      )}
      {size.w > 0 && data.nodes.length > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={size.w}
          height={size.h}
          graphData={data}
          backgroundColor="#ffffff"
          cooldownTicks={80}
          onEngineStop={() => fgRef.current?.zoomToFit(300, 50)}
          linkColor={() => "rgba(17,17,17,0.35)"}
          linkWidth={1.2}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          linkLabel={(l) => (l as TLink).kind}
          onNodeClick={(node) => onSelect((node as TNode).id)}
          nodeCanvasObject={(node, ctx, scale) => {
            const n = node as TNode;
            const x = n.x ?? 0;
            const y = n.y ?? 0;
            const isAnswer = n.id === answerNodeId;
            const isSelected = n.id === selectedId;
            const r = isAnswer ? 9 : 7;

            if (isSelected) {
              ctx.beginPath();
              ctx.arc(x, y, r + 4, 0, 2 * Math.PI);
              ctx.strokeStyle = "#3b9ab8";
              ctx.lineWidth = 2;
              ctx.stroke();
            }
            ctx.beginPath();
            ctx.arc(x, y, r, 0, 2 * Math.PI);
            ctx.fillStyle = isAnswer ? "#3b9ab8" : "#ffffff";
            ctx.fill();
            ctx.strokeStyle = "#111111";
            ctx.lineWidth = 1.2;
            ctx.stroke();

            const fontSize = Math.max(8, 10 / scale);
            ctx.font = `700 ${fontSize}px "JetBrains Mono", monospace`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillStyle = isAnswer ? "#ffffff" : "#111111";
            ctx.fillText(String(n.order), x, y);

            const caption = n.caption.length > 26 ? n.caption.slice(0, 25) + "…" : n.caption;
            ctx.font = `500 ${fontSize}px "JetBrains Mono", monospace`;
            ctx.textBaseline = "top";
            ctx.fillStyle = "#111111";
            ctx.fillText(caption, x, y + r + 3);
          }}
          nodePointerAreaPaint={(node, color, ctx) => {
            const n = node as TNode;
            ctx.beginPath();
            ctx.arc(n.x ?? 0, n.y ?? 0, 12, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
          }}
        />
      )}
    </div>
  );
}
