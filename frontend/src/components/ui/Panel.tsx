import type { PropsWithChildren, ReactNode } from "react";

interface PanelProps {
  title: ReactNode;
  /** Chữ nhỏ phía phải tiêu đề (số liệu, đường dẫn...). */
  meta?: ReactNode;
  className?: string;
  bodyClassName?: string;
}

/** Panel kiểu dashboard: thanh tiêu đề chữ hoa + meta, thân bên dưới. */
export function Panel({
  title,
  meta,
  className = "",
  bodyClassName = "",
  children,
}: PropsWithChildren<PanelProps>) {
  return (
    <section className={`flex flex-col rounded-sm border border-line bg-white ${className}`}>
      <header className="flex items-center justify-between gap-3 border-b border-line px-3 py-2">
        <h2 className="text-[11px] font-bold uppercase tracking-wider">{title}</h2>
        {meta && <div className="text-[11px] text-neutral-500">{meta}</div>}
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
