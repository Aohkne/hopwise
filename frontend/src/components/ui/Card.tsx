import type { PropsWithChildren } from "react";

/** Primitive neo-brutalism: border rõ nét + box-shadow, bo góc 8px. */
export function Card({ children, className = "" }: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={`rounded-brutal border-2 border-brutal-border bg-white p-4 shadow-brutal ${className}`}
    >
      {children}
    </div>
  );
}
