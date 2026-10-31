import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d";
import { getNode, type GraphPayload } from "../../api/client";
import { Panel } from "../ui/Panel";
import { NodeDetailCard } from "./NodeDetailCard";

// Màu theo label, cố định qua hash (mỗi label 1 màu). Bảng màu teal/đen/xám
// khớp phong cách dashboard.
const PALETTE = [
  "#3b9ab8", "#111111", "#9ca3af", "#7cc4d8",
  "#1f6f8b", "#d1d5db", "#5b6770", "#a8dadc",
];
const BORDER = "#111111";

function colorForLabel(label: string): string {
  let hash = 0;
  for (let i = 0; i < label.length; i++) hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

interface GNode {
  id: string;
  label: string;
  caption: string;
  degree: number;
  x?: number;
  y?: number;
}

interface GEdge {
  source: string | GNode;
  target: string | GNode;
  kind: string;
}

function endpoints(e: GEdge): [string, string] {
  const s = typeof e.source === "string" ? e.source : e.source.id;
  const t = typeof e.target === "string" ? e.target : e.target.id;
  return [s, t];
}

type LabelBox = { x1: number; y1: number; x2: number; y2: number };
const overlaps = (a: LabelBox, b: LabelBox) =>
  a.x1 < b.x2 && a.x2 > b.x1 && a.y1 < b.y2 && a.y2 > b.y1;

interface GraphViewProps {
  domain: string;
  payload: GraphPayload | null;
  error: string | null;
}

/**
 * Vẽ TOÀN BỘ Knowledge Graph của 1 domain (payload do GraphPage tải) bằng `react-force-graph-2d`: layout lực tự nhiên, node tròn vẽ bằng canvas,
 * viền đen không đổ bóng. Kích thước node theo bậc (số cạnh). Hover làm mờ
 * phần không liên quan; nhãn tự né nhau (xem pattern từ graph-demo).
 * Bấm vào node: card ảnh + thông tin chi tiết hiện góc phải trên, bên trong
 * khung graph (ảnh mặc định nếu node không có ảnh).
 */
export function GraphView({ domain, payload, error }: GraphViewProps) {
  const [focused, setFocused] = useState<{ id: string; label: string; props: Record<string, unknown> } | null>(null);
  const [hoverNode, setHoverNode] = useState<GNode | null>(null);

  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const fgRef = useRef<ForceGraphMethods<GNode, GEdge> | undefined>(undefined);
  const labelBoxesRef = useRef<LabelBox[]>([]);

  const current = payload;
  const focusedId = focused?.id ?? null;

  // Đổi domain -> bỏ card chi tiết của node domain cũ.
  const [prevDomain, setPrevDomain] = useState(domain);
  if (prevDomain !== domain) {
    setPrevDomain(domain);
    setFocused(null);
  }

  const graphData = useMemo(() => {
    if (!current) return { nodes: [] as GNode[], links: [] as GEdge[] };
    const degree = new Map<string, number>();
    for (const e of current.edges) {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    }
    const nodes: GNode[] = current.nodes.map((n) => ({
      id: n.id,
      label: n.label,
      caption: n.caption ?? n.id,
      degree: degree.get(n.id) ?? 0,
    }));
    const links: GEdge[] = current.edges.map((e) => ({ ...e }));
    return { nodes, links };
  }, [current]);

  const labels = useMemo(
    () => [...new Set(graphData.nodes.map((n) => n.label))].sort(),
    [graphData]
  );

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  // Node đang được làm nổi: node hover, nếu không thì node đã bấm (card chi tiết đang mở).
  const spotlightId = hoverNode?.id ?? focusedId;

  // id của mọi node kề với node được làm nổi, để tô đậm + làm mờ phần còn lại
  const hoverConnected = useMemo(() => {
    if (!spotlightId) return null;
    const set = new Set<string>();
    for (const e of graphData.links) {
      const [s, t] = endpoints(e);
      if (s === spotlightId) set.add(t);
      else if (t === spotlightId) set.add(s);
    }
    return set;
  }, [spotlightId, graphData]);

  const isLinkActive = useCallback(
    (e: GEdge) => {
      if (!spotlightId) return false;
      const [s, t] = endpoints(e);
      return s === spotlightId || t === spotlightId;
    },
    [spotlightId]
  );

  const focus = useCallback(async (node: GNode) => {
    const nodeId = node.id;
    // Camera đẩy vào node được bấm để các node kề hiện rõ nhãn.
    if (node.x !== undefined && node.y !== undefined) {
      fgRef.current?.centerAt(node.x, node.y, 700);
      fgRef.current?.zoom(3, 700);
    }
    try {
      const detail = await getNode(nodeId);
      setFocused({ id: nodeId, label: detail.label, props: detail.properties });
    } catch {
      setFocused(null);
    }
  }, []);

  return (
    <Panel
      title={
        <span className="flex items-center gap-3">
          <span className="bg-neutral-900 px-2 py-0.5 text-white">GRAPH</span>
          <span className="font-normal normal-case text-neutral-500">/{domain}</span>
        </span>
      }
      meta={
        current
          ? `${current.nodes.length} node · ${current.edges.length} cạnh · ${labels.length} loại`
          : error
            ? "Không tải được graph"
            : "Đang tải graph…"
      }
      className="min-h-[420px] flex-1"
      bodyClassName="relative"
    >
      {error && <p className="p-3 text-xs text-red-700">{error}</p>}
      {current && current.nodes.length === 0 && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-1 text-center">
          <p className="text-sm font-bold">Chưa có dữ liệu</p>
          <p className="text-xs text-neutral-500">
            Kéo thả tài liệu .txt / .md vào đây, hoặc bấm “Upload tài liệu”.
          </p>
        </div>
      )}

      <div
        ref={wrapRef}
        className="absolute inset-0 overflow-hidden bg-white"
      >
        {size.w > 0 && current && (
          <ForceGraph2D
            ref={fgRef}
            width={size.w}
            height={size.h}
            graphData={graphData}
            backgroundColor="#ffffff"
            nodeRelSize={5}
            cooldownTicks={200}
            onEngineStop={() => fgRef.current?.zoomToFit(400, 60)}
            onRenderFramePre={() => {
              labelBoxesRef.current = [];
            }}
            onNodeHover={(node) => {
              setHoverNode((node as GNode | null) ?? null);
              if (wrapRef.current) wrapRef.current.style.cursor = node ? "pointer" : "default";
            }}
            onNodeClick={(node) => void focus(node as GNode)}
            linkColor={(l) => (isLinkActive(l as GEdge) ? "#3b9ab8" : "rgba(17,17,17,0.14)")}
            linkWidth={(l) => (isLinkActive(l as GEdge) ? 2 : 0.6)}
            linkDirectionalArrowLength={(l) => (isLinkActive(l as GEdge) ? 5 : 0)}
            linkDirectionalArrowRelPos={1}
            nodeCanvasObject={(node, ctx, scale) => {
              const n = node as GNode;
              const isHover = spotlightId === n.id;
              const isNeighbor = hoverConnected?.has(n.id) ?? false;
              const dimmed = !!spotlightId && !isHover && !isNeighbor;

              const r = 3 + Math.min(Math.sqrt(n.degree), 9) + (isHover ? 2 : 0);
              const x = n.x ?? 0;
              const y = n.y ?? 0;

              ctx.save();
              ctx.globalAlpha = dimmed ? 0.15 : 1;
              ctx.beginPath();
              ctx.arc(x, y, r, 0, 2 * Math.PI);
              ctx.fillStyle = colorForLabel(n.label);
              ctx.fill();
              ctx.strokeStyle = BORDER;
              ctx.lineWidth = isHover || n.id === focusedId ? 2 : 0.8;
              ctx.stroke();

              const showLabel = isHover || isNeighbor || n.id === focusedId || scale > 2.2;
              if (!dimmed && showLabel) {
                const label = n.caption.length > 28 ? n.caption.slice(0, 27) + "…" : n.caption;
                const fontSize = 11 / scale; // cỡ chữ cố định trên màn hình, không phình to khi zoom
                ctx.font = `${isHover ? 700 : 500} ${fontSize}px "JetBrains Mono", monospace`;
                const textW = ctx.measureText(label).width;
                const padX = 4;
                const box: LabelBox = {
                  x1: x - textW / 2 - padX,
                  y1: y + r + 2,
                  x2: x + textW / 2 + padX,
                  y2: y + r + 2 + fontSize + 3,
                };
                if (!labelBoxesRef.current.some((b) => overlaps(box, b))) {
                  labelBoxesRef.current.push(box);
                  ctx.fillStyle = "rgba(255,255,255,0.92)";
                  ctx.fillRect(box.x1, box.y1, box.x2 - box.x1, box.y2 - box.y1);
                  ctx.textAlign = "center";
                  ctx.textBaseline = "top";
                  ctx.fillStyle = BORDER;
                  ctx.fillText(label, x, box.y1 + 1.5);
                }
              }
              ctx.restore();
            }}
            nodePointerAreaPaint={(node, color, ctx) => {
              const n = node as GNode;
              ctx.beginPath();
              ctx.arc(n.x ?? 0, n.y ?? 0, 3 + Math.min(Math.sqrt(n.degree), 9) + 3, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
            }}
          />
        )}
      </div>

      {labels.length > 0 && (
        <div className="pointer-events-none absolute bottom-2 left-3 z-10 flex max-w-[60%] flex-wrap gap-x-3 gap-y-1 bg-white/90 px-2 py-1 text-[10px] text-neutral-600">
          {labels.map((label) => (
            <span key={label} className="flex items-center gap-1">
              <i
                className="inline-block size-2.5 rounded-full border border-neutral-900"
                style={{ background: colorForLabel(label) }}
              />
              {label}
            </span>
          ))}
        </div>
      )}

      {focused && (
        <NodeDetailCard
          key={focused.id}
          label={focused.label}
          properties={focused.props}
          onClose={() => setFocused(null)}
        />
      )}
    </Panel>
  );
}
