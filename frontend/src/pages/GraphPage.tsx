import { Icon } from "@iconify/react";
import { useMemo, useState } from "react";
import { GraphView } from "../components/graph/GraphView";
import { Button } from "../components/ui/Button";
import { StatStrip, type Stat } from "../components/ui/StatStrip";
import { useDomainGraph } from "../hooks/useDomainGraph";

const DOMAINS = [
  { value: "football_vn", label: "Bóng đá Việt Nam" },
  { value: "vinfast", label: "VinFast" },
];

export function GraphPage() {
  const [domain, setDomain] = useState(DOMAINS[0].value);
  const { payload, error } = useDomainGraph(domain);

  const stats = useMemo<Stat[]>(() => {
    const dash = "—";
    if (!payload) {
      return ["NODES", "EDGES", "NODE TYPES", "EDGE TYPES", "AVG DEGREE", "MAX DEGREE"].map(
        (label) => ({ label, value: dash })
      );
    }
    const degree = new Map<string, number>();
    for (const e of payload.edges) {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    }
    const max = Math.max(0, ...degree.values());
    const avg = payload.nodes.length ? (2 * payload.edges.length) / payload.nodes.length : 0;
    return [
      { label: "NODES", value: payload.nodes.length.toLocaleString("en-US") },
      { label: "EDGES", value: payload.edges.length.toLocaleString("en-US") },
      { label: "NODE TYPES", value: new Set(payload.nodes.map((n) => n.label)).size },
      { label: "EDGE TYPES", value: new Set(payload.edges.map((e) => e.kind)).size },
      { label: "AVG DEGREE", value: avg.toFixed(2) },
      { label: "MAX DEGREE", value: max },
    ];
  }, [payload]);

  return (
    <div className="flex h-[calc(100vh-57px)] w-full flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-bold tracking-wide">
          GRAPH <span className="font-normal text-neutral-400">// knowledge cortex</span>
        </h1>
        <label className="ml-auto text-xs" htmlFor="domain-select">
          Domain:
        </label>
        <select
          id="domain-select"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          className="rounded-sm border border-line bg-white px-2 py-1 text-xs"
        >
          {DOMAINS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
        <Button
          disabled
          title="Chưa triển khai — phụ thuộc cơ chế tạo cạnh bằng fact (xem Bản 2.0.0 trong TODO.md)"
          className="cursor-not-allowed opacity-50"
        >
          <Icon icon="mdi:upload" className="mr-1 inline size-3.5" />
          Upload tài liệu
        </Button>
      </div>

      <StatStrip stats={stats} />
      <GraphView domain={domain} payload={payload} error={error} />
    </div>
  );
}
