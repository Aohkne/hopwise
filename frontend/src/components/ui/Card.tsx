import type { PropsWithChildren } from "react";

/** Khối nội dung: viền mảnh 1px, góc vuông nhẹ, không đổ bóng. */
export function Card({ children, className = "" }: PropsWithChildren<{ className?: string }>) {
  return <div className={`rounded-sm border border-line bg-white p-4 ${className}`}>{children}</div>;
}
