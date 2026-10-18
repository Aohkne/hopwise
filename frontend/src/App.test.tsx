import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { mockFetchRoutes } from "./test/fetchMock";

beforeEach(() => {
  mockFetchRoutes([
    [/graph\/domains/, () => ({ nodes: [], edges: [] })],
    [/benchmark\/models/, () => ({ jev: "typesafe/jev-1.13", ollama: { model: "gemma4:12b", version: null }, nvidia: { model: "openai/gpt-oss-20b" } })],
    [/benchmark\/history/, () => []],
  ]);
});
afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("renders without crashing, defaults to Graph tab", () => {
    render(<App />);
    expect(screen.getByText("Hopwise")).toBeInTheDocument();
    expect(screen.getByLabelText("Domain:")).toBeInTheDocument();
  });

  it("switches to Benchmark tab on click", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /benchmark/i }));
    expect(screen.getByLabelText("Câu hỏi")).toBeInTheDocument();
  });
});
