import { Icon } from "@iconify/react";
import { useState } from "react";
import { GraphView } from "../components/graph/GraphView";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";

const DOMAINS = [
  { value: "football_vn", label: "Bóng đá Việt Nam" },
  { value: "vinfast", label: "VinFast" },
];

export function GraphPage() {
  const [domain, setDomain] = useState(DOMAINS[0].value);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <Card className="flex flex-wrap items-center gap-3">
        <label className="text-sm font-semibold" htmlFor="domain-select">
          Domain:
        </label>
        <select
          id="domain-select"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          className="rounded-brutal border-2 border-brutal-border bg-white px-2 py-1 text-sm"
        >
          {DOMAINS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>

        <Button
          disabled
          title="Chưa triển khai — phụ thuộc cơ chế tạo cạnh bằng fact (xem Bản 2.0.0 trong TODO.md)"
          className="ml-auto cursor-not-allowed opacity-50"
        >
          <Icon icon="mdi:upload" className="mr-1 inline size-4" />
          Upload tài liệu
        </Button>
      </Card>

      <GraphView domain={domain} />
    </div>
  );
}
