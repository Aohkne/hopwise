import type { ButtonHTMLAttributes } from "react";

/** Primitive neo-brutalism: border rõ nét + box-shadow, bo góc 8px. */
export function Button({
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`rounded-brutal border-2 border-brutal-border bg-brutal-accent px-4 py-2
        font-semibold text-white shadow-brutal transition-transform
        active:translate-x-1 active:translate-y-1 active:shadow-none ${className}`}
      {...props}
    />
  );
}
