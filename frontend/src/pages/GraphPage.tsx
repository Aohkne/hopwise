import { Icon } from "@iconify/react";
import { useCallback, useMemo, useRef, useState, type DragEvent } from "react";
import { GraphView } from "../components/graph/GraphView";
import { Button } from "../components/ui/Button";
import { StatStrip, type Stat } from "../components/ui/StatStrip";
import { useDocumentUpload } from "../hooks/useDocumentUpload";
import { useDomainGraph } from "../hooks/useDomainGraph";
import type { DocumentJob } from "../api/client";

const DOMAINS = [
  { value: "football_vn", label: "Bóng đá Việt Nam" },
  { value: "vinfast", label: "VinFast" },
  { value: "vinfast_policy", label: "VinFast · chính sách (từ văn bản)" },
];

/** Domain nhận tài liệu upload: graph sinh từ văn bản nằm riêng, không lẫn vào dữ liệu crawl. */
const UPLOAD_DOMAIN = "vinfast_policy";

export function GraphPage() {
  const [domain, setDomain] = useState(DOMAINS[0].value);
  const [reloadKey, setReloadKey] = useState(0);
  const { payload, error } = useDomainGraph(domain, reloadKey);
  const fileInput = useRef<HTMLInputElement>(null);

  // Upload xong: chuyển sang domain vừa nhận tài liệu và tải lại graph.
  const onUploaded = useCallback((job: DocumentJob) => {
    setDomain(job.domain);
    setReloadKey((k) => k + 1);
  }, []);
  const upload = useDocumentUpload(UPLOAD_DOMAIN, onUploaded);

  // Kéo thả file vào trang = chọn file bằng nút Upload.
  const [dragging, setDragging] = useState(false);
  const hasFiles = (e: DragEvent<HTMLElement>) => e.dataTransfer.types.includes("Files");

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
    <div
      className="relative flex h-[calc(100vh-57px)] w-full flex-col gap-3 p-4"
      onDragOver={(e) => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false);
      }}
      onDrop={(e) => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        setDragging(false);
        const file = e.dataTransfer.files[0];
        if (file && !upload.busy) void upload.upload(file);
      }}
    >
      {dragging && (
        <div
          data-testid="drop-overlay"
          className="pointer-events-none absolute inset-2 z-50 flex items-center justify-center border-2 border-dashed border-teal-dark bg-white/80 text-sm font-bold"
        >
          Thả tài liệu để thêm vào graph
        </div>
      )}
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
        <input
          ref={fileInput}
          type="file"
          accept=".txt,.md,text/plain,text/markdown"
          aria-label="Chọn tài liệu"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = ""; // chọn lại cùng file vẫn kích hoạt onChange
            if (file) void upload.upload(file);
          }}
        />
        <Button
          disabled={upload.busy}
          onClick={() => fileInput.current?.click()}
          title="Trích xuất Entity / Relationship / Claim từ file .txt / .md rồi thêm vào graph"
          className="disabled:cursor-wait disabled:opacity-50"
        >
          <Icon icon="mdi:upload" className="mr-1 inline size-3.5" />
          Upload tài liệu
        </Button>
      </div>

      <StatStrip stats={stats} />
      {upload.busy && (
        <p role="status" className="text-xs text-neutral-600">
          Đang trích xuất {upload.job?.name ?? "tài liệu"}
          {upload.job && upload.job.total_chunks > 0
            ? ` — ${upload.job.done_chunks}/${upload.job.total_chunks} đoạn`
            : "…"}
        </p>
      )}
      {upload.error && (
        <p role="alert" className="text-xs text-red-700">
          Upload thất bại: {upload.error}
        </p>
      )}
      {upload.job?.status === "done" && upload.job.report && !upload.busy && (
        <p role="status" className="text-xs text-teal-dark">
          Đã thêm {upload.job.report.entities} entity, {upload.job.report.relationships} relationship,{" "}
          {upload.job.report.claims} claim từ {upload.job.name}
          {upload.job.report.skipped.length + upload.job.report.errors.length > 0 &&
            ` (${upload.job.report.skipped.length + upload.job.report.errors.length} record/đoạn bị bỏ)`}
        </p>
      )}
      <GraphView domain={domain} payload={payload} error={error} />
    </div>
  );
}
