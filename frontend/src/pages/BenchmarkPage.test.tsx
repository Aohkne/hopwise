import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockFetchRoutes } from "../test/fetchMock";
import { BenchmarkPage } from "./BenchmarkPage";

const step = (n: number, id: string, caption: string, via: string | null = null) => ({
  step: n, phase: "visit", node_id: id, node_label: "Company", node_caption: caption,
  from_node_id: via ? "vf8" : null, via_edge: via, latency_ms: 600, tokens: 10, cost: 0.00001,
});

const result = (model: string, status: string) => ({
  model, model_name: `${model}-name`, status,
  model_version: model === "jev" && status !== "running" ? "typesafe/jev-1.13-20260917" : null,
  answer_node_id: status === "found" ? "vinfast" : null,
  answer_text: status === "found" ? "VinFast" : null,
  error: status === "error" ? "Thiếu API key" : null,
  elapsed_ms: 2200, tokens: 20, cost: 0.0001, domain: "vinfast", label: "CarModel",
  steps: status === "found"
    ? [step(1, "vf8", "VinFast VF 8"), step(2, "vinfast", "VinFast — hãng xe", "MANUFACTURES (in)")]
    : [],
});

const doneRun = {
  id: "r1", question: "Xe VF8 của công ty nào?", started_at: "2026-10-17T10:00:00+00:00",
  status: "done", llm_model: "google/gemini-3.8-flash",
  models: { jev: result("jev", "found"), llm: result("llm", "error") },
};

const MODELS = {
  llm: ["google/gemini-3.8-flash"],
  jev: "typesafe/jev-1.13",
};

afterEach(() => vi.unstubAllGlobals());

describe("BenchmarkPage", () => {
  it("runs 2 models, shows statuses, and highlights a traced node when selected", async () => {
    const fetchMock = mockFetchRoutes([
      [/benchmark\/models/, () => MODELS],
      [/benchmark\/history/, () => []],
      [/benchmark\/runs\/r1$/, () => doneRun],
      [/benchmark\/runs$/, () => ({ ...doneRun, status: "running",
        models: { jev: result("jev", "running"), llm: result("llm", "running") } })],
    ]);
    render(<BenchmarkPage />);

    await waitFor(() => expect(screen.getByLabelText("Model LLM")).toHaveValue("google/gemini-3.8-flash"));
    // phiên bản hiện cả khi chưa chạy: Jev theo cấu hình
    expect(screen.getAllByText("typesafe/jev-1.13").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("Câu hỏi"), { target: { value: "Xe VF8 của công ty nào?" } });
    fireEvent.click(screen.getByRole("button", { name: "Chạy" }));

    expect(await screen.findByRole("button", { name: "Dừng" })).toBeInTheDocument();
    const posted = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(posted![1]!.body))).toEqual({
      question: "Xe VF8 của công ty nào?", llm_model: "google/gemini-3.8-flash",
    });

    // poll -> lượt chạy xong
    expect(await screen.findByText("1/2", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getAllByText("VinFast")).toHaveLength(1);
    expect(screen.getByText("Thiếu API key")).toBeInTheDocument();
    // sau khi chạy: Jev hiện phiên bản thật OpenRouter trả về
    expect(screen.getAllByText("typesafe/jev-1.13-20260917").length).toBeGreaterThan(0);

    // tab "Node đã đi qua" của hàng JEV, chọn 1 node -> dòng đó được viền
    const tabs = screen.getAllByRole("tab", { name: /Node đã đi qua \(2\)/ });
    fireEvent.click(tabs[0]);
    const item = screen.getAllByText("VinFast — hãng xe")[0].closest("li")!;
    expect(item).not.toHaveAttribute("aria-current");
    fireEvent.click(item);
    expect(item).toHaveAttribute("aria-current", "true");
    expect(within(item).getByText("qua MANUFACTURES (in)")).toBeInTheDocument();
  });

  it("history tab lists past runs and opens one", async () => {
    mockFetchRoutes([
      [/benchmark\/models/, () => MODELS],
      [/benchmark\/history/, () => [doneRun]],
      [/benchmark\/runs\/r1$/, () => doneRun],
    ]);
    render(<BenchmarkPage />);

    fireEvent.click(await screen.findByRole("tab", { name: "Lịch sử (1)" }));
    fireEvent.click(screen.getByText("Xe VF8 của công ty nào?"));
    expect(await screen.findByText("câu hỏi:")).toBeInTheDocument();
    expect(screen.getAllByText("VinFast").length).toBeGreaterThan(0);
  });
});
