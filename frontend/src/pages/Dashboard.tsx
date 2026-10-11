import { Icon } from "@iconify/react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { GraphView } from "../components/graph/GraphView";

/** TODO: chọn domain + chạy benchmark — xem TODO.md. */
export function Dashboard() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <Card className="flex items-center gap-3">
        <Icon icon="mdi:graph-outline" className="size-8 text-brutal-accent" />
        <div>
          <h1 className="text-xl font-bold">Hopwise</h1>
          <p className="text-sm text-neutral-600">
            So sánh Jev/Kev (System 1) với LLM thường (System 2) trên Knowledge Graph.
          </p>
        </div>
      </Card>

      <GraphView />

      <Card className="flex items-center justify-between">
        <span className="text-sm text-neutral-600">
          TODO: chọn domain + chạy benchmark — xem TODO.md.
        </span>
        <Button disabled>Chạy benchmark</Button>
      </Card>
    </div>
  );
}
