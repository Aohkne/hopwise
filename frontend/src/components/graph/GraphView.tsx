import { Card } from "../ui/Card";

/** TODO: hiển thị Knowledge Graph thật (node/cạnh từ backend) — xem TODO.md. */
export function GraphView() {
  return (
    <Card>
      <p className="text-sm text-neutral-600">
        TODO: hiển thị Knowledge Graph (gọi <code>GET /graph/nodes/:id/neighbors</code>{" "}
        từ backend) — xem TODO.md.
      </p>
    </Card>
  );
}
