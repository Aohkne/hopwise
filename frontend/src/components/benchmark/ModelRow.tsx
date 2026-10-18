import { useEffect, useRef, useState } from "react";
import type { ModelResult, TraceStep } from "../../api/client";
import { Panel } from "../ui/Panel";
import { correctness, formatMs, STATUS_CLASS, STATUS_TEXT } from "./status";
import { TraceGraph } from "./TraceGraph";

interface Props {
  title: string;
  result: ModelResult | null;
  /** Phiên bản model hiển thị cạnh tên (VD "typesafe/jev-1.13-20260917"). */
  version?: string | null;
}

type RightTab = "status" | "nodes";

/** 1 hàng model: trái là graph đã đi qua, phải là tab Status / Node đã đi qua.
 * Bấm node bên graph -> chuyển sang tab Node và viền dòng tương ứng. */
export function ModelRow({ title, result, version }: Props) {
  const [tab, setTab] = useState<RightTab>("status");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const itemRefs = useRef(new Map<string, HTMLLIElement>());

  const steps: TraceStep[] = result?.steps ?? [];
  const visits = steps.filter((s) => s.phase === "visit" && s.node_id);

  useEffect(() => {
    if (tab === "nodes" && selectedId) {
      itemRefs.current.get(selectedId)?.scrollIntoView?.({ block: "nearest" });
    }
  }, [tab, selectedId]);

  function selectFromGraph(nodeId: string) {
    setSelectedId(nodeId);
    setTab("nodes");
  }

  const status = result?.status;
  const verdict = correctness(result?.correct);

  return (
    <Panel
      title={
        <span className="flex items-center gap-3">
          {title}
          {version && (
            <span className="rounded-sm border border-line px-1.5 py-0.5 font-normal normal-case text-neutral-600">
              {version}
            </span>
          )}
          {status && (
            <span className={`rounded-sm border px-1.5 py-0.5 font-medium normal-case ${STATUS_CLASS[status]}`}>
              {STATUS_TEXT[status]}
            </span>
          )}
          {verdict && (
            <span
              title="so với ground truth"
              className={`rounded-sm border px-1.5 py-0.5 font-bold normal-case ${verdict.className}`}
            >
              {verdict.text}
            </span>
          )}
        </span>
      }
      meta={result?.model_name ?? "chưa chạy"}
    >
      <div className="grid md:grid-cols-[minmax(0,1fr)_380px]">
        <div className="h-72 border-b border-line md:border-r md:border-b-0">
          <TraceGraph
            steps={steps}
            answerNodeId={result?.answer_node_id ?? null}
            selectedId={selectedId}
            onSelect={selectFromGraph}
          />
        </div>

        <div className="flex h-72 flex-col">
          <div role="tablist" className="flex border-b border-line text-[11px]">
            {(
              [
                ["status", "Status"],
                ["nodes", `Node đã đi qua (${visits.length})`],
              ] as [RightTab, string][]
            ).map(([id, label]) => (
              <button
                key={id}
                role="tab"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
                className={`px-3 py-1.5 ${
                  tab === id ? "border-b-2 border-teal font-bold text-teal-dark" : "text-neutral-500"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-3 text-xs">
            {tab === "status" ? (
              <dl className="space-y-1.5">
                {(
                  [
                    ["đáp án", result?.answer_text ?? "—"],
                    ["ground truth", verdict ? verdict.text : "—"],
                    ["phiên bản", result?.model_version ?? version ?? "—"],
                    ["thời gian", result ? formatMs(result.elapsed_ms) : "—"],
                    ["số lần gọi", result ? steps.length || result.calls || 0 : "—"],
                    ["tokens", result ? result.tokens.toLocaleString("en-US") : "—"],
                    ["chi phí", result ? `$${result.cost.toFixed(6)}` : "—"],
                    ["domain", result?.domain ?? "—"],
                    ["loại node", result?.label ?? "—"],
                  ] as [string, string | number][]
                ).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3">
                    <dt className="text-neutral-500">o {k}</dt>
                    <dd className="truncate text-right" title={String(v)}>
                      {v}
                    </dd>
                  </div>
                ))}
                {result?.error && <p className="pt-1 text-red-700">{result.error}</p>}
              </dl>
            ) : visits.length === 0 ? (
              <p className="text-neutral-400">chưa đi tới node nào</p>
            ) : (
              <ol className="space-y-1">
                {visits.map((s, i) => {
                  const selected = s.node_id === selectedId;
                  return (
                    <li
                      key={`${s.node_id}-${i}`}
                      ref={(el) => {
                        if (el && s.node_id) itemRefs.current.set(s.node_id, el);
                      }}
                      aria-current={selected ? "true" : undefined}
                      onClick={() => setSelectedId(s.node_id ?? null)}
                      className={`cursor-pointer rounded-sm border px-2 py-1.5 ${
                        selected ? "border-2 border-teal bg-teal-soft" : "border-line hover:bg-neutral-50"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold">#{i + 1}</span>
                        <span className="text-[10px] text-neutral-500">{s.node_label}</span>
                        <span className="ml-auto text-[10px] text-neutral-400">
                          {formatMs(s.latency_ms)}
                        </span>
                      </div>
                      <div className="truncate" title={s.node_caption ?? ""}>
                        {s.node_caption}
                      </div>
                      {s.via_edge && (
                        <div className="text-[10px] text-neutral-500">qua {s.via_edge}</div>
                      )}
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
        </div>
      </div>
    </Panel>
  );
}
