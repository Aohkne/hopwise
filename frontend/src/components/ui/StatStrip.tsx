export interface Stat {
  label: string;
  value: string | number;
  hint?: string;
}

/** Dải số liệu ở đầu trang (TASKS / TOOL CALLS / ... trong hình mẫu). */
export function StatStrip({ stats }: { stats: Stat[] }) {
  return (
    <div
      className="grid divide-x divide-line rounded-sm border border-line bg-white"
      style={{ gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))` }}
    >
      {stats.map((s) => (
        <div key={s.label} className="px-3 py-2">
          <div className="text-[10px] uppercase tracking-wider text-neutral-500">{s.label}</div>
          <div className="mt-0.5 text-2xl font-medium leading-tight">{s.value}</div>
          {s.hint && <div className="text-[10px] text-neutral-400">{s.hint}</div>}
        </div>
      ))}
    </div>
  );
}
