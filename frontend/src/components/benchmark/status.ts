import type { RunStatus } from "../../api/client";

export const STATUS_TEXT: Record<RunStatus, string> = {
  running: "đang chạy",
  found: "tìm ra",
  not_found: "không tìm ra",
  timeout: "quá 5 phút",
  stopped: "đã dừng",
  error: "lỗi",
};

export const STATUS_CLASS: Record<RunStatus, string> = {
  running: "border-teal text-teal-dark animate-pulse",
  found: "border-teal-dark bg-teal text-white",
  not_found: "border-line text-neutral-500",
  timeout: "border-amber-500 text-amber-700",
  stopped: "border-line text-neutral-500",
  error: "border-red-400 text-red-700",
};

export function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`;
}
