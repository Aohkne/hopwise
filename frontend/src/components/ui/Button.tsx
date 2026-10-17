import type { ButtonHTMLAttributes } from "react";

/** Nút teal, góc vuông nhẹ, không đổ bóng. */
export function Button({ className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`rounded-sm border border-teal-dark bg-teal px-3 py-1.5 text-xs font-medium
        text-white transition-colors hover:bg-teal-dark ${className}`}
      {...props}
    />
  );
}
