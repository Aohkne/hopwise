import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d";
import { getNeighbors, getNode, searchNodes, type SearchResult } from "../../api/client";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

// Node gốc mặc định hiện ngay khi vào trang, theo domain — không bắt tìm
// kiếm trước. id lấy trực tiếp từ data/*.json (Company VinFast, đội tuyển
// quốc gia bóng đá VN).
const DEFAULT_ROOTS: Record<string, string> = {
  vinfast: "Q56660561_vinfast",
  football_vn: "Q270689_đội_tuyển_bóng_đá_quốc_gia_việt_nam",
};

// Màu theo label, cố định qua hash — giống quy ước Neo4j Browser (mỗi
// label 1 màu riêng). Viền đen dày + "shadow" cứng vẽ tay bên dưới mỗi
// node để khớp phong cách neo-brutalism của Card/Button còn lại.
const PALETTE = [
  "#93c5fd", "#86efac", "#fca5a5", "#fdba74",
  "#c4b5fd", "#67e8f9", "#f9a8d4", "#fde68a",
];
const BORDER = "#111111";

function colorForLabel(label: string): string {
  let hash = 0;
  for (let i = 0; i < label.length; i++) hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

interface GNode {
  id: string;
  label: string; // label Neo4j (Player, Club, Company...)
  caption: string;
  x?: number;
  y?: number;
}

interface GEdge {
  source: string | GNode;
  target: string | GNode;
  kind: string;
  label: string;
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
}

/**
 * Vẽ Knowledge Graph bằng `react-force-graph-2d` — layout lực hấp dẫn/đẩy
 * tự nhiên (không phải tự tính x/y tay), node hình tròn vẽ bằng canvas,
 * viền đen dày + shadow cứng theo đúng style neo-brutalism của Card/Button.
 * Pattern (hover làm mờ phần không liên quan, click mở rộng giữ nguyên vị
 * trí node cũ để không giật layout, né nhãn chữ đè nhau) tham khảo từ
 * graph-demo (dự án trước, cùng kiến trúc Neo4j + FastAPI + React).
 *
 * Vào trang là thấy graph ngay (root mặc định theo domain, xem
 * DEFAULT_ROOTS) — ô tìm kiếm chỉ để nhảy sang node khác, không bắt buộc.
 * Lưu ý: tìm kiếm hiện tìm trên TOÀN BỘ graph, chưa lọc theo `domain` —
 * backend chưa gắn nhãn domain cho node (xem TODO.md).
 */
export function GraphView({ domain }: GraphViewProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [focusedDetail, setFocusedDetail] = useState<Record<string, unknown> | null>(null);
  const [hoverNode, setHoverNode] = useState<GNode | null>(null);

  const [nodes, setNodes] = useState<GNode[]>([]);
  const [edges, setEdges] = useState<GEdge[]>([]);

  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const fgRef = useRef<ForceGraphMethods<GNode, GEdge> | undefined>(undefined);
  const expandedRef = useRef<Set<string>>(new Set());
  const labelBoxesRef = useRef<LabelBox[]>([]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  // id của mọi node kề với node đang hover, để làm nổi bật + làm mờ phần còn lại
  const hoverConnected = useMemo(() => {
    if (!hoverNode) return null;
    const set = new Set<string>();
    for (const e of edges) {
      const [s, t] = endpoints(e);
      if (s === hoverNode.id) set.add(t);
      else if (t === hoverNode.id) set.add(s);
    }
    return set;
  }, [hoverNode, edges]);

  const isLinkActive = useCallback(
    (e: GEdge) => {
      if (!hoverNode) return false;
      const [s, t] = endpoints(e);
      return s === hoverNode.id || t === hoverNode.id;
    },
    [hoverNode]
  );

  const focus = useCallback(async (nodeId: string) => {
    try {
      const detail = await getNode(nodeId);
      setFocusedId(nodeId);
      setFocusedDetail(detail.properties);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  const expand = useCallback(async (nodeId: string) => {
    if (expandedRef.current.has(nodeId)) return;
    expandedRef.current.add(nodeId);

    try {
      const neighbors = await getNeighbors(nodeId);

      // Giữ nguyên object node cũ (không tạo mới) để lực mô phỏng không bị
      // reset vị trí những node đã ổn định.
      setNodes((prev) => {
        const byId = new Map(prev.map((n) => [n.id, n]));
        for (const n of neighbors) {
          if (!byId.has(n.target_id)) {
            byId.set(n.target_id, {
              id: n.target_id,
              label: n.target_label,
              caption: n.target_description ?? n.target_id,
            });
          }
        }
        return [...byId.values()];
      });

      setEdges((prev) => {
        const key = (e: GEdge) => {
          const [s, t] = endpoints(e);
          return `${s}->${t}:${e.kind}`;
        };
        const map = new Map(prev.map((e) => [key(e), e]));
        neighbors.forEach((n) => {
          const e: GEdge = { source: nodeId, target: n.target_id, kind: n.edge_type, label: n.edge_type };
          const k = key(e);
          if (!map.has(k)) map.set(k, e);
        });
        return [...map.values()];
      });
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  const loadRoot = useCallback(async (nodeId: string) => {
    expandedRef.current.clear();

    try {
      const detail = await getNode(nodeId);
      setError(null);
      setNodes([{
        id: nodeId,
        label: detail.label,
        // Ưu tiên description giống node con (neighbor chỉ có
        // target_description, không có name) — 2 domain hiện dùng field
        // tên khác nhau (name vs name_vi) nên không đồng nhất nếu ưu tiên
        // name ở riêng node gốc.
        caption: String(detail.properties.description ?? nodeId),
      }]);
      setEdges([]);
      setResults([]);
      setQuery("");
      setFocusedId(nodeId);
      setFocusedDetail(detail.properties);
      await expand(nodeId);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [expand]);

  // Đổi domain -> tự load node gốc mặc định của domain đó, không bắt tìm
  // kiếm trước.
  useEffect(() => {
    const rootId = DEFAULT_ROOTS[domain];
    // react-hooks/set-state-in-effect: rule này flag mọi pattern "effect gọi
    // hàm async rồi hàm đó setState", kể cả fetch-on-dependency-change kinh
    // điển (xem react.dev/learn/synchronizing-with-effects#fetching-data).
    // Sửa đúng ý rule cần chuyển sang Suspense/`use()`, quá lớn so với scope
    // hiện tại — suppress có chủ đích, không phải bỏ qua lỗi không hiểu.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (rootId) void loadRoot(rootId);
  }, [domain, loadRoot]);

  function onSearchChange(value: string) {
    setQuery(value);
    if (value.trim().length < 2) {
      setResults([]);
      return;
    }
    searchNodes(value).then(setResults).catch((e: Error) => setError(e.message));
  }

  return (
    <div className="flex flex-col gap-3">
      {error && <Card className="border-red-600 bg-red-50 text-sm text-red-700">{error}</Card>}

      <Card>
        <div className="flex items-center gap-2">
          <input
            className="flex-1 rounded-brutal border-2 border-brutal-border px-3 py-2 text-sm"
            placeholder="Tìm node khác để nhảy sang (VD: Nguyễn Quang Hải, Hà Nội...)"
            value={query}
            onChange={(e) => onSearchChange(e.target.value)}
          />
          <Button className="px-3 py-2 text-xs" onClick={() => void loadRoot(DEFAULT_ROOTS[domain])}>
            Về gốc
          </Button>
        </div>
        <p className="mt-1 text-xs text-neutral-400">
          Tìm trên toàn bộ graph, chưa lọc theo domain &ldquo;{domain}&rdquo; — xem TODO.md.
        </p>
        {results.length > 0 && (
          <ul className="mt-2 flex flex-col gap-1">
            {results.map((r) => (
              <li key={r.id}>
                <button
                  className="w-full rounded-brutal border-2 border-brutal-border bg-white
                    px-3 py-2 text-left text-sm hover:bg-neutral-100"
                  onClick={() => void loadRoot(r.id)}
                >
                  <span className="mr-2 rounded bg-neutral-200 px-1.5 py-0.5 text-xs">
                    {r.label}
                  </span>
                  {r.description}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div
        ref={wrapRef}
        className="h-[480px] w-full overflow-hidden rounded-brutal border-2 border-brutal-border shadow-brutal"
      >
        {size.w > 0 && (
          <ForceGraph2D
            ref={fgRef}
            width={size.w}
            height={size.h}
            graphData={{ nodes, links: edges }}
            backgroundColor="#fdf6e3"
            nodeRelSize={5}
            cooldownTicks={120}
            onEngineStop={() => fgRef.current?.zoomToFit(300, 40)}
            onRenderFramePre={() => {
              labelBoxesRef.current = [];
            }}
            onNodeHover={(node) => {
              setHoverNode((node as GNode | null) ?? null);
              if (wrapRef.current) wrapRef.current.style.cursor = node ? "pointer" : "default";
            }}
            onNodeClick={(node) => {
              void focus(node.id);
              void expand(node.id);
            }}
            linkColor={(l) => {
              const e = l as GEdge;
              const active = isLinkActive(e);
              return active ? BORDER : "rgba(17,17,17,0.25)";
            }}
            linkWidth={(l) => (isLinkActive(l as GEdge) ? 2.5 : 1)}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            nodeCanvasObject={(node, ctx, scale) => {
              const n = node as GNode;
              const isRoot = focusedId !== null && nodes[0]?.id === n.id;
              const isHover = hoverNode?.id === n.id;
              const isNeighbor = hoverConnected?.has(n.id) ?? false;
              const dimmed = !!hoverNode && !isHover && !isNeighbor;

              const r = (isRoot ? 11 : 8) + (isHover ? 2 : isNeighbor ? 1 : 0);
              const x = n.x ?? 0;
              const y = n.y ?? 0;

              ctx.save();
              ctx.globalAlpha = dimmed ? 0.2 : 1;

              // shadow cứng kiểu neo-brutalism (offset, không blur)
              ctx.beginPath();
              ctx.arc(x + 2.5, y + 2.5, r, 0, 2 * Math.PI);
              ctx.fillStyle = BORDER;
              ctx.fill();

              ctx.beginPath();
              ctx.arc(x, y, r, 0, 2 * Math.PI);
              ctx.fillStyle = colorForLabel(n.label);
              ctx.fill();
              ctx.strokeStyle = BORDER;
              ctx.lineWidth = isHover ? 3 : 2;
              ctx.stroke();

              if (!dimmed && (isHover || isNeighbor || scale > 1.1)) {
                const label = n.caption.length > 28 ? n.caption.slice(0, 27) + "…" : n.caption;
                const fontSize = Math.max(9, 11 / scale);
                ctx.font = `${isHover ? 700 : 500} ${fontSize}px Inter, sans-serif`;
                const textW = ctx.measureText(label).width;
                const padX = 4;
                const box: LabelBox = {
                  x1: x - textW / 2 - padX,
                  y1: y + r + 2,
                  x2: x + textW / 2 + padX,
                  y2: y + r + 2 + fontSize + 3,
                };
                const free = !labelBoxesRef.current.some((b) => overlaps(box, b));
                if (free) {
                  labelBoxesRef.current.push(box);
                  ctx.fillStyle = "rgba(253,246,227,0.9)";
                  ctx.fillRect(box.x1, box.y1, box.x2 - box.x1, box.y2 - box.y1);
                  ctx.textAlign = "center";
                  ctx.textBaseline = "top";
                  ctx.fillStyle = "#111111";
                  ctx.fillText(label, x, box.y1 + 1.5);
                }
              }

              ctx.restore();
            }}
            nodePointerAreaPaint={(node, color, ctx) => {
              const n = node as GNode;
              ctx.beginPath();
              ctx.arc(n.x ?? 0, n.y ?? 0, 12, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
            }}
          />
        )}
      </div>

      {focusedId && focusedDetail && (
        <Card>
          <h2 className="mb-1 font-semibold">
            {String(focusedDetail.name ?? focusedDetail.name_vi ?? focusedId)}
          </h2>
          <p className="text-sm text-neutral-600">{String(focusedDetail.description ?? "")}</p>
        </Card>
      )}
    </div>
  );
}
