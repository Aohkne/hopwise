import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NodeDetailCard } from "./NodeDetailCard";
import { pickImage, pickRows } from "./nodeDetail";

describe("NodeDetailCard", () => {
  it("shows the node image and key details", () => {
    render(
      <NodeDetailCard
        label="Player"
        properties={{
          name_vi: "An",
          image_url: "https://x/y.png",
          dob: "01/01/2000",
          position: "Tiền vệ",
          description: "Mô tả",
        }}
        onClose={() => {}}
      />
    );
    expect(screen.getByRole("img", { name: "An" })).toHaveAttribute("src", "https://x/y.png");
    expect(screen.getByText("01/01/2000")).toBeInTheDocument();
    expect(screen.getByText("Tiền vệ")).toBeInTheDocument();
    expect(screen.getByText("Player")).toBeInTheDocument();
    expect(screen.getByText("Mô tả")).toBeInTheDocument();
  });

  it("falls back to the default image when the node has none", () => {
    render(<NodeDetailCard label="Club" properties={{ name_vi: "CLB" }} onClose={() => {}} />);
    expect(screen.getByLabelText("Ảnh mặc định")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "CLB" })).not.toBeInTheDocument();
  });

  it("falls back to the default image when the image fails to load, and closes", () => {
    const onClose = vi.fn();
    render(
      <NodeDetailCard
        label="Club"
        properties={{ name_vi: "CLB", image_url: "https://broken" }}
        onClose={onClose}
      />
    );
    fireEvent.error(screen.getByRole("img", { name: "CLB" }));
    expect(screen.getByLabelText("Ảnh mặc định")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Đóng"));
    expect(onClose).toHaveBeenCalled();
  });

  it("pickImage uses logo_urls when there is no image_url", () => {
    expect(pickImage({ logo_urls: ["https://logo"] })).toBe("https://logo");
    expect(pickImage({})).toBeNull();
  });

  it("pickRows skips empty and object values and caps at 6", () => {
    const rows = pickRows({ dob: "x", position: "", nationality: null, age: { a: 1 }, title: "t" });
    expect(rows).toEqual([["dob", "x"], ["title", "t"]]);
  });
});

describe("NodeDetailCard — Claim", () => {
  it("shows the claim's status, dates, condition and source quote", () => {
    render(
      <NodeDetailCard
        label="Claim"
        properties={{
          claim_type: "DISCOUNT",
          status: "TRUE",
          start_date: "2026-01-15",
          end_date: "2026-01-20",
          condition: "mua xe",
          source_text: "VF3 giảm 30% từ 15 đến 20/01",
          description: "VF3 được giảm 30%",
        }}
        onClose={() => {}}
      />
    );
    expect(screen.getByText("DISCOUNT", { selector: "span" })).toBeInTheDocument(); // tiêu đề
    for (const text of ["TRUE", "2026-01-15", "2026-01-20", "mua xe", "VF3 giảm 30% từ 15 đến 20/01"]) {
      expect(screen.getByText(text)).toBeInTheDocument();
    }
    expect(screen.getByText("VF3 được giảm 30%")).toBeInTheDocument();
  });
});
