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

function mockFetch(impl: (url: string, init?: RequestInit) => Promise<Response>) {
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

  it("treats a domain with no data (404) as an empty graph with a hint, not an error", async () => {
    mockFetch(async () => new Response(JSON.stringify({ detail: "Domain 'x' không có dữ liệu" }), { status: 404 }));
    render(<GraphPage />);
    expect(await screen.findByText("Chưa có dữ liệu")).toBeInTheDocument();
    expect(screen.queryByText("Không tải được graph")).not.toBeInTheDocument();
  });

  describe("upload tài liệu", () => {
    const done = {
      id: "j1", name: "tb.md", domain: "vinfast_policy", status: "done", done_chunks: 2, total_chunks: 2,
      error: null,
      report: { entities: 7, relationships: 5, claims: 3, chunks: 2, domain: "vinfast_policy", skipped: ["x"], errors: [] },
    };

    function mockBackend(post: () => Response) {
      return mockFetch(async (url, init) => {
        if (url.endsWith("/graph/documents") && init?.method === "POST") return post();
        if (url.includes("/graph/documents/j1")) return new Response(JSON.stringify(done));
        return new Response(JSON.stringify(payload));
      });
    }

    function pick(file: File) {
      fireEvent.change(screen.getByLabelText("Chọn tài liệu"), { target: { files: [file] } });
    }

    it("enables the button, sends the file text, then switches to the new domain and reloads", async () => {
      const running = { ...done, status: "running", done_chunks: 0, total_chunks: 0, report: null };
      const fetchMock = mockBackend(() => new Response(JSON.stringify(running)));
      render(<GraphPage />);
      await screen.findByText("3 node · 2 cạnh · 2 loại");
      expect(screen.getByRole("button", { name: /Upload tài liệu/ })).toBeEnabled();

      pick(new File(["VF3 giảm 30%"], "tb.md", { type: "text/markdown" }));

      expect(await screen.findByRole("status")).toHaveTextContent("Đang trích xuất tb.md");
      const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")!;
      expect(JSON.parse(post[1]!.body as string)).toEqual({
        name: "tb.md", text: "VF3 giảm 30%", domain: "vinfast_policy",
      });
      expect(screen.getByRole("button", { name: /Upload tài liệu/ })).toBeDisabled();

      // poll xong (1,5 giây): báo kết quả, chọn domain mới, tải lại graph của domain đó
      expect(await screen.findByText(/Đã thêm 7 entity, 5 relationship, 3 claim từ tb.md/, {}, { timeout: 4000 }))
        .toHaveTextContent("(1 record/đoạn bị bỏ)");
      expect(screen.getByLabelText("Domain:")).toHaveValue("vinfast_policy");
      await waitFor(() =>
        expect(fetchMock).toHaveBeenCalledWith("/api/v1/graph/domains/vinfast_policy")
      );
      expect(screen.getByRole("button", { name: /Upload tài liệu/ })).toBeEnabled();
    });

    it("accepts a file dropped on the page and shows the drop overlay while dragging", async () => {
      const fetchMock = mockBackend(() => new Response(JSON.stringify(done)));
      const { container } = render(<GraphPage />);
      await screen.findByText("3 node · 2 cạnh · 2 loại");
      const page = container.firstElementChild!;
      const file = new File(["VF3 giảm 30%"], "tb.md", { type: "text/markdown" });
      const dataTransfer = { types: ["Files"], files: [file] };

      fireEvent.dragOver(page, { dataTransfer });
      expect(screen.getByTestId("drop-overlay")).toBeInTheDocument();
      fireEvent.drop(page, { dataTransfer });
      expect(screen.queryByTestId("drop-overlay")).not.toBeInTheDocument();

      await waitFor(() => {
        const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")!;
        expect(JSON.parse(post[1]!.body as string)).toMatchObject({ name: "tb.md", text: "VF3 giảm 30%" });
      });
    });

    it("ignores drags that carry no file", async () => {
      mockBackend(() => new Response(JSON.stringify(done)));
      const { container } = render(<GraphPage />);
      await screen.findByText("3 node · 2 cạnh · 2 loại");
      fireEvent.dragOver(container.firstElementChild!, { dataTransfer: { types: ["text/plain"], files: [] } });
      expect(screen.queryByTestId("drop-overlay")).not.toBeInTheDocument();
    });

    it("shows the reason when the backend rejects the file", async () => {
      mockBackend(() => new Response(JSON.stringify({ detail: "Văn bản trống" }), { status: 422 }));
      render(<GraphPage />);
      await screen.findByText("3 node · 2 cạnh · 2 loại");
      pick(new File([" "], "rong.txt"));
      expect(await screen.findByRole("alert")).toHaveTextContent("Upload thất bại: Văn bản trống");
      expect(screen.getByRole("button", { name: /Upload tài liệu/ })).toBeEnabled();
    });
  });
});

