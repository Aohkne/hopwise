import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockFetchRoutes } from "../test/fetchMock";
import { BenchmarkPage } from "./BenchmarkPage";

const step = (n: number, id: string, caption: string, via: string | null = null) => ({
  step: n, phase: "visit", node_id: id, node_label: "Company", node_caption: caption,
  from_node_id: via ? "vf8" : null, via_edge: via, latency_ms: 600, tokens: 10, cost: 0.00001,
});

const result = (model: string, status: string, extra: Record<string, unknown> = {}) => ({
  model, model_name: `${model}-name`, status,
  model_version: model === "jev" && status !== "running" ? "typesafe/jev-1.13-20260917" : null,
  answer_node_id: status === "found" ? "vinfast" : null,
  answer_text: status === "found" ? "VinFast" : null,
  error: status === "error" ? "Thiếu API key" : null,
  elapsed_ms: 2200, tokens: 20, cost: 0.0001, domain: "vinfast", label: "CarModel",
  steps: status === "found"
    ? [step(1, "vf8", "VinFast VF 8"), step(2, "vinfast", "VinFast — hãng xe", "MANUFACTURES (in)")]
    : [],
  ...extra,
});

const doneRun = {
  id: "r1", question: "Xe VF8 của công ty nào?", started_at: "2026-10-17T10:00:00+00:00",
  status: "done",
  case_id: "vinfast-008", expected_answers: ["vinfast"],
  models: {
    jev: result("jev", "found", { correct: true }),
    ollama: result("ollama", "found", { correct: false, answer_text: "Vingroup" }),
    nvidia: result("nvidia", "error"),
  },
};

const MODELS = {
  jev: "typesafe/jev-1.13",
  ollama: { model: "gemma4:12b", version: "gemma4:12b · 11.9B · Q4_K_M" },
  nvidia: { model: "openai/gpt-oss-20b" },
};
const CASES = [
  { id: "vinfast-008", domain: "vinfast", question: "Xe VF 8 của công ty nào?", hops: 1 },
];

afterEach(() => vi.unstubAllGlobals());

describe("BenchmarkPage", () => {
  it("runs 3 models, shows statuses, and highlights a traced node when selected", async () => {
    const fetchMock = mockFetchRoutes([
      [/benchmark\/models/, () => MODELS],
      [/benchmark\/cases/, () => CASES],
      [/benchmark\/history/, () => []],
      [/benchmark\/runs\/r1$/, () => doneRun],
      [/benchmark\/runs$/, () => ({ ...doneRun, status: "running",
        models: { jev: result("jev", "running"), ollama: result("ollama", "running"),
                  nvidia: result("nvidia", "running") } })],
    ]);
    render(<BenchmarkPage />);

    // phiên bản hiện cả khi chưa chạy: Jev và NVIDIA theo cấu hình, Gemma hỏi từ Ollama
    await waitFor(() => expect(screen.getAllByText("openai/gpt-oss-20b").length).toBeGreaterThan(0));
    expect(screen.getAllByText("typesafe/jev-1.13").length).toBeGreaterThan(0);
    expect(screen.getAllByText("gemma4:12b · 11.9B · Q4_K_M").length).toBeGreaterThan(0);
    expect(screen.queryByLabelText("Model LLM")).not.toBeInTheDocument();  // không còn dropdown
    fireEvent.change(screen.getByLabelText("Câu hỏi"), { target: { value: "Xe VF8 của công ty nào?" } });
    fireEvent.click(screen.getByRole("button", { name: "Chạy" }));

    expect(await screen.findByRole("button", { name: "Dừng" })).toBeInTheDocument();
    const posted = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(posted![1]!.body))).toEqual({ question: "Xe VF8 của công ty nào?" });

    // poll -> lượt chạy xong
    expect(await screen.findByText("2/3", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getAllByText("VinFast")).toHaveLength(1);  // Ollama trả Vingroup, NVIDIA lỗi
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

  it("runs a ground-truth case and shows correct / wrong verdicts", async () => {
    const fetchMock = mockFetchRoutes([
      [/benchmark\/models/, () => MODELS],
      [/benchmark\/cases/, () => CASES],
      [/benchmark\/history/, () => []],
      [/benchmark\/runs\/r1$/, () => doneRun],
      [/benchmark\/runs$/, () => ({ ...doneRun, status: "running" })],
    ]);
    render(<BenchmarkPage />);

    const select = await screen.findByLabelText("Câu hỏi mẫu (ground truth)");
    await waitFor(() => expect(screen.getByText(/vinfast-008 · 1 bước/)).toBeInTheDocument());
    fireEvent.change(select, { target: { value: "vinfast-008" } });
    expect(screen.getByLabelText("Câu hỏi")).toHaveValue("Xe VF 8 của công ty nào?");

    fireEvent.click(screen.getByRole("button", { name: "Chạy" }));
    await screen.findByRole("button", { name: "Dừng" });
    const posted = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(posted![1]!.body)).case_id).toBe("vinfast-008");

    expect(await screen.findByText("1/2", {}, { timeout: 3000 })).toBeInTheDocument(); // CORRECT
    // huy hiệu trên tiêu đề + dòng "ground truth" trong tab Status
    expect(screen.getAllByText("đúng")).toHaveLength(2);
    expect(screen.getAllByText("sai")).toHaveLength(2);
  });

  it("editing the question detaches it from the ground-truth case", async () => {
    const fetchMock = mockFetchRoutes([
      [/benchmark\/models/, () => MODELS],
      [/benchmark\/cases/, () => CASES],
      [/benchmark\/history/, () => []],
      [/benchmark\/runs$/, () => ({ ...doneRun, status: "running" })],
    ]);
    render(<BenchmarkPage />);
    const select = await screen.findByLabelText("Câu hỏi mẫu (ground truth)");
    await waitFor(() => expect(screen.getByText(/vinfast-008 · 1 bước/)).toBeInTheDocument());
    fireEvent.change(select, { target: { value: "vinfast-008" } });
    fireEvent.change(screen.getByLabelText("Câu hỏi"), { target: { value: "Câu khác" } });
    expect(select).toHaveValue("");

    fireEvent.click(screen.getByRole("button", { name: "Chạy" }));
    await screen.findByRole("button", { name: "Dừng" });
    const posted = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(posted![1]!.body))).not.toHaveProperty("case_id");
  });

  it("shows the error message of a model that failed", async () => {
    mockFetchRoutes([
      [/benchmark\/models/, () => MODELS],
      [/benchmark\/cases/, () => CASES],
      [/benchmark\/history/, () => [{ ...doneRun, models: { jev: doneRun.models.jev, nvidia: result("nvidia", "error") } }]],
      [/benchmark\/runs\/r1$/, () => ({ ...doneRun, models: { jev: doneRun.models.jev, nvidia: result("nvidia", "error") } })],
    ]);
    render(<BenchmarkPage />);
    fireEvent.click(await screen.findByRole("tab", { name: "Lịch sử (1)" }));
    fireEvent.click(screen.getByText("Xe VF8 của công ty nào?"));
    expect(await screen.findByText("Thiếu API key")).toBeInTheDocument();
  });

  it("history tab lists past runs and opens one", async () => {
    mockFetchRoutes([
      [/benchmark\/models/, () => MODELS],
      [/benchmark\/cases/, () => CASES],
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
