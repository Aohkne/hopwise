import { Icon } from "@iconify/react";

export type Tab = "graph" | "benchmark";

interface NavbarProps {
  active: Tab;
  onChange: (tab: Tab) => void;
}

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "graph", label: "Graph", icon: "mdi:graph-outline" },
  { id: "benchmark", label: "Benchmark", icon: "mdi:scale-balance" },
];

export function Navbar({ active, onChange }: NavbarProps) {
  return (
    <nav className="flex items-center gap-2 border-b-2 border-brutal-border bg-white px-4 py-3">
      <span className="mr-4 flex items-center gap-2 font-bold">
        <Icon icon="mdi:graph-outline" className="size-6 text-brutal-accent" />
        Hopwise
      </span>
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`flex items-center gap-1.5 rounded-brutal border-2 border-brutal-border
            px-3 py-1.5 text-sm font-semibold transition-colors ${
              active === tab.id
                ? "bg-brutal-accent text-white shadow-brutal"
                : "bg-white hover:bg-neutral-100"
            }`}
        >
          <Icon icon={tab.icon} />
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
