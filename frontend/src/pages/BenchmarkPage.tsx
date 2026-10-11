import { useState } from "react";
import { ModelPanel } from "../components/benchmark/ModelPanel";
import { Card } from "../components/ui/Card";

// TODO: lấy từ BASELINE_MODELS trong .env qua backend thay vì hardcode.
const LLM_OPTIONS = ["openai/gpt-6-sol", "google/gemini-3.8-flash", "deepseek/deepseek-v4.1-flash"];

export function BenchmarkPage() {
  const [query, setQuery] = useState("");
  const [llmModel, setLlmModel] = useState(LLM_OPTIONS[0]);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4 p-6">
      <Card>
        <label className="mb-2 block text-sm font-semibold" htmlFor="benchmark-query">
          Câu hỏi / node bắt đầu
        </label>
        <input
          id="benchmark-query"
          className="w-full rounded-brutal border-2 border-brutal-border px-3 py-2"
          placeholder="VD: VinFast, Nguyễn Quang Hải..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <ModelPanel title="Jev" />
        <ModelPanel title="Kev (local)" />
        <ModelPanel
          title="LLM"
          modelSelect={
            <select
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              className="rounded-brutal border-2 border-brutal-border bg-white px-2 py-1 text-xs"
            >
              {LLM_OPTIONS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          }
        />
      </div>
    </div>
  );
}
