import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  getRun,
  listHistory,
  listModels,
  startRun,
  stopRun,
  type BenchmarkRun,
  type ModelKey,
  type ModelsInfo,
} from "../api/client";
import { ModelRow } from "../components/benchmark/ModelRow";
import { formatMs, STATUS_CLASS, STATUS_TEXT } from "../components/benchmark/status";
import { Button } from "../components/ui/Button";
import { Panel } from "../components/ui/Panel";
import { StatStrip, type Stat } from "../components/ui/StatStrip";

const POLL_MS = 1000;
const ROWS: [ModelKey, string][] = [
  ["jev", "JEV"],
  ["llm", "LLM"],
];

type View = "run" | "history";

function runStats(run: BenchmarkRun | null, historyCount: number): Stat[] {
  const results = run ? Object.values(run.models) : [];
  const found = results.filter((r) => r.status === "found");
  const fastest = found.length ? Math.min(...found.map((r) => r.elapsed_ms)) : null;
  const calls = results.reduce((n, r) => n + (r.steps?.length ?? r.calls ?? 0), 0);
  const tokens = results.reduce((n, r) => n + r.tokens, 0);
  const cost = results.reduce((n, r) => n + r.cost, 0);
  return [
    { label: "RUNS", value: historyCount },
    { label: "FOUND", value: run ? `${found.length}/${results.length}` : "—" },
    { label: "FASTEST", value: formatMs(fastest) },
    { label: "CALLS", value: run ? calls : "—" },
    { label: "TOKENS", value: run ? tokens.toLocaleString("en-US") : "—" },
    { label: "COST", value: run ? `$${cost.toFixed(5)}` : "—" },
  ];
}

/** Phiên bản hiển thị: ưu tiên bản thật model đã trả lời trong lượt chạy, nếu
 * chưa chạy thì theo cấu hình (Jev) / LLM đang chọn. */
function versionOf(key: ModelKey, run: BenchmarkRun | null, info: ModelsInfo | null,
                   llmModel?: string): string | null {
  const r = run?.models[key];
  if (r?.model_version) return r.model_version;
  if (key === "llm") return r?.model_name ?? llmModel ?? null;
  return info?.[key] ?? r?.model_name ?? null;
}

function ModelRows({ run, info, llmModel, modelSelect }: {
  run: BenchmarkRun | null;
  info: ModelsInfo | null;
  llmModel?: string;
  modelSelect?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3">
      {ROWS.map(([key, title]) => (
        <ModelRow
          key={`${run?.id ?? "empty"}-${key}`}
          title={title}
          result={run?.models[key] ?? null}
          version={versionOf(key, run, info, llmModel)}
          modelSelect={key === "llm" ? modelSelect : undefined}
        />
      ))}
    </div>
  );
}

export function BenchmarkPage() {
  const [view, setView] = useState<View>("run");
  const [question, setQuestion] = useState("");
  const [info, setInfo] = useState<ModelsInfo | null>(null);
  const [llmModel, setLlmModel] = useState("");
  const [run, setRun] = useState<BenchmarkRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<BenchmarkRun[]>([]);
  const [historyRun, setHistoryRun] = useState<BenchmarkRun | null>(null);

  const running = run?.status === "running";

  const refreshHistory = useCallback(() => {
    listHistory()
      .then((h) => setHistory(h ?? []))
      .catch(() => setHistory([]));
  }, []);

  useEffect(() => {
    listModels()
      .then((models) => {
        setInfo(models);
        setLlmModel((current) => current || models?.llm?.[0] || "");
      })
      .catch((e: Error) => setError(e.message));
    refreshHistory();
  }, [refreshHistory]);

  // Poll lượt đang chạy tới khi xong, rồi làm mới lịch sử (CSV vừa ghi).
  useEffect(() => {
    if (!run || run.status !== "running") return;
    const timer = setInterval(() => {
      getRun(run.id)
        .then((next) => {
          setRun(next);
          if (next.status === "done") refreshHistory();
        })
        .catch((e: Error) => setError(e.message));
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [run, refreshHistory]);

  async function onStart() {
    setError(null);
    try {
      setRun(await startRun(question, llmModel));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function onStop() {
    if (run) await stopRun(run.id).catch((e: Error) => setError(e.message));
  }

  async function openHistory(id: string) {
    try {
      setHistoryRun(await getRun(id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const stats = useMemo(
    () => runStats(view === "run" ? run : historyRun, history.length),
    [view, run, historyRun, history.length]
  );

  const llmSelect = (
    <select
      aria-label="Model LLM"
      value={llmModel}
      disabled={running}
      onChange={(e) => setLlmModel(e.target.value)}
      className="rounded-sm border border-line bg-white px-1.5 py-0.5 text-[11px] normal-case"
    >
      {(info?.llm ?? []).map((m) => (
        <option key={m} value={m}>
          {m}
        </option>
      ))}
    </select>
  );

  return (
    <div className="flex w-full flex-col gap-3 p-4">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-bold tracking-wide">
          BENCHMARK <span className="font-normal text-neutral-400">// system 1 vs system 2</span>
        </h1>
        <div role="tablist" className="ml-auto flex gap-1">
          {(
            [
              ["run", "Chạy"],
              ["history", `Lịch sử (${history.length})`],
            ] as [View, string][]
          ).map(([id, label]) => (
            <button
              key={id}
              role="tab"
              aria-selected={view === id}
              onClick={() => setView(id)}
              className={`rounded-sm border px-3 py-1 text-xs ${
                view === id ? "border-teal-dark bg-teal text-white" : "border-line bg-white"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <StatStrip stats={stats} />
      {error && <p className="text-xs text-red-700">{error}</p>}

      {view === "run" ? (
        <>
          <Panel title="QUERY" meta="2 model chạy song song · tối đa 5 phút mỗi model">
            <div className="flex flex-wrap items-end gap-3 p-3">
              <div className="min-w-[280px] flex-1">
                <label className="mb-1 block text-[11px] text-neutral-500" htmlFor="benchmark-query">
                  Câu hỏi
                </label>
                <input
                  id="benchmark-query"
                  className="w-full rounded-sm border border-line px-3 py-2 text-xs focus:border-teal focus:outline-none"
                  placeholder="VD: Xe VF8 của công ty nào?"
                  value={question}
                  disabled={running}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && question.trim() && !running) void onStart();
                  }}
                />
              </div>
              {running ? (
                <Button onClick={() => void onStop()} className="border-red-700 bg-red-600 hover:bg-red-700">
                  Dừng
                </Button>
              ) : (
                <Button onClick={() => void onStart()} disabled={!question.trim() || !llmModel}>
                  Chạy
                </Button>
              )}
            </div>
          </Panel>
          <ModelRows run={run} info={info} llmModel={llmModel} modelSelect={llmSelect} />
        </>
      ) : (
        <div className="grid gap-3 lg:grid-cols-[320px_minmax(0,1fr)]">
          <Panel title="LỊCH SỬ" meta="outputs/runs.csv">
            {history.length === 0 ? (
              <p className="p-3 text-xs text-neutral-400">chưa có lượt chạy nào</p>
            ) : (
              <ul className="max-h-[70vh] divide-y divide-line overflow-y-auto">
                {history.map((h) => (
                  <li key={h.id}>
                    <button
                      onClick={() => void openHistory(h.id)}
                      className={`w-full px-3 py-2 text-left text-xs hover:bg-teal-soft ${
                        historyRun?.id === h.id ? "bg-teal-soft" : ""
                      }`}
                    >
                      <div className="truncate font-medium">{h.question}</div>
                      <div className="text-[10px] text-neutral-400">{h.started_at}</div>
                      <div className="mt-1 flex gap-1">
                        {ROWS.map(([key]) => {
                          const r = h.models[key];
                          return r ? (
                            <span
                              key={key}
                              className={`rounded-sm border px-1 text-[10px] ${STATUS_CLASS[r.status]}`}
                            >
                              {key} {STATUS_TEXT[r.status]}
                            </span>
                          ) : null;
                        })}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          {historyRun ? (
            <div className="flex flex-col gap-3">
              <p className="text-xs">
                <span className="text-neutral-500">câu hỏi:</span> {historyRun.question}
              </p>
              <ModelRows run={historyRun} info={null} />
            </div>
          ) : (
            <p className="p-3 text-xs text-neutral-400">chọn 1 lượt bên trái để xem lại</p>
          )}
        </div>
      )}
    </div>
  );
}
