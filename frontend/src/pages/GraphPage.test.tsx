import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GraphPage } from "./GraphPage";

const payload = {
  nodes: [
    { id: "a", label: "Company", caption: "A" },
    { id: "b", label: "CarModel", caption: "B" },
    { id: "c", label: "CarModel", caption: null },
  ],
  edges: [
    { source: "a", target: "b", kind: "MANUFACTURES" },
    { source: "a", target: "c", kind: "MANUFACTURES" },
  ],
};

function mockFetch(impl: (url: string) => Promise<Response>) {
  const fn = vi.fn(impl);
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("GraphPage", () => {
  it("loads the whole domain graph with no search step and shows real stats", async () => {
    const fetchMock = mockFetch(async () => new Response(JSON.stringify(payload)));
    render(<GraphPage />);

    expect(await screen.findByText("3 node · 2 cạnh · 2 loại")).toBeInTheDocument();
    expect(screen.getByText("Company")).toBeInTheDocument();
    expect(screen.getByText("CarModel")).toBeInTheDocument();
    // AVG DEGREE = 2*2/3, MAX DEGREE = 2 (node "a")
    expect(screen.getByText("1.33")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/graph/domains/football_vn");
    expect(screen.queryByPlaceholderText(/tìm/i)).not.toBeInTheDocument();
  });

  it("reloads when the domain changes", async () => {
    const fetchMock = mockFetch(async () => new Response(JSON.stringify(payload)));
    render(<GraphPage />);
    await screen.findByText("3 node · 2 cạnh · 2 loại");
    fireEvent.change(screen.getByLabelText("Domain:"), { target: { value: "vinfast" } });
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/v1/graph/domains/vinfast")
    );
  });

  it("shows an error when the backend fails", async () => {
    mockFetch(async () => new Response("nope", { status: 500 }));
    render(<GraphPage />);
    expect(await screen.findByText("Không tải được graph")).toBeInTheDocument();
    expect(screen.getByText(/failed: 500/)).toBeInTheDocument();
  });
});
