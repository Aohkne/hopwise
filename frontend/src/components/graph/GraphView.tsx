import { Card } from "../ui/Card";

interface GraphViewProps {
  domain: string;
}

/** TODO: vẽ sơ đồ node-cạnh thật (React Flow) cho domain đã chọn — xem TODO.md.
 * Chờ backend có GET /api/v1/graph/search, /nodes/{id}, /nodes/{id}/neighbors. */
export function GraphView({ domain }: GraphViewProps) {
  return (
    <Card>
      <p className="text-sm text-neutral-600">
        TODO: hiển thị Knowledge Graph cho domain <code>{domain}</code> (gọi{" "}
        <code>GET /api/v1/graph/...</code> từ backend) — xem TODO.md.
      </p>
    </Card>
  );
}
