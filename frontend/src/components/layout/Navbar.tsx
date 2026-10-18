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
    <nav className="flex w-full items-center gap-3 border-b border-line bg-white px-5 py-3">
      <span className="pixel-title mr-6 text-2xl">Hopwise</span>
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`flex items-center gap-2 rounded-sm border px-3 py-1.5 text-xs font-medium
            transition-colors ${
              active === tab.id
                ? "border-teal-dark bg-teal text-white"
                : "border-line bg-white hover:bg-teal-soft"
            }`}
        >
          <Icon icon={tab.icon} className="size-4" />
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
