import { Icon } from "@iconify/react";
import { useState } from "react";
import { pickImage, pickRows } from "./nodeDetail";

interface Props {
  label: string;
  properties: Record<string, unknown>;
  onClose: () => void;
}

/** Card chi tiết node, đặt chồng góc phải trên của khung graph: ảnh (hoặc ảnh
 * mặc định nếu không có / tải lỗi) + các thông tin chính. */
export function NodeDetailCard({ label, properties, onClose }: Props) {
  const image = pickImage(properties);
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const showImage = image !== null && failedSrc !== image;
  const title = String(properties.name ?? properties.name_vi ?? properties.id ?? "");
  const rows = pickRows(properties);

  return (
    <aside className="absolute top-3 right-3 z-10 w-72 rounded-sm border border-teal bg-white">
      <header className="flex items-center justify-between bg-teal px-3 py-1.5 text-white">
        <span className="truncate text-xs font-bold" title={title}>
          {title}
        </span>
        <button onClick={onClose} aria-label="Đóng" className="ml-2 hover:opacity-70">
          <Icon icon="mdi:close" className="size-4" />
        </button>
      </header>

      <div className="flex h-36 items-center justify-center border-b border-line bg-neutral-100">
        {showImage ? (
          <img
            src={image}
            alt={title}
            referrerPolicy="no-referrer"
            onError={() => setFailedSrc(image)}
            className="h-full w-full object-contain"
          />
        ) : (
          <svg
            role="img"
            aria-label="Ảnh mặc định"
            viewBox="0 0 24 24"
            className="size-10 text-neutral-300"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <rect x="3" y="4" width="18" height="16" rx="1" />
            <circle cx="9" cy="10" r="1.6" />
            <path d="M3 17l5-4 4 3 3-2 6 4" />
          </svg>
        )}
      </div>

      <dl className="space-y-1 px-3 py-2 text-[11px]">
        <div className="flex justify-between gap-3">
          <dt className="text-neutral-500">o type</dt>
          <dd>{label}</dd>
        </div>
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3">
            <dt className="text-neutral-500">o {k}</dt>
            <dd className="truncate text-right" title={v}>
              {v}
            </dd>
          </div>
        ))}
      </dl>
      {typeof properties.description === "string" && (
        <p className="border-t border-line px-3 py-2 text-[11px] leading-snug text-neutral-600">
          {properties.description}
        </p>
      )}
    </aside>
  );
}
