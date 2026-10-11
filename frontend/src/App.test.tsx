import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("renders without crashing, defaults to Graph tab", () => {
    render(<App />);
    expect(screen.getByText("Hopwise")).toBeInTheDocument();
    expect(screen.getByLabelText("Domain:")).toBeInTheDocument();
  });

  it("switches to Benchmark tab on click", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /benchmark/i }));
    expect(screen.getByLabelText("Câu hỏi / node bắt đầu")).toBeInTheDocument();
  });
});
