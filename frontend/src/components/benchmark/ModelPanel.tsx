import type { ReactNode } from "react";
import { Card } from "../ui/Card";

interface ModelPanelProps {
  title: string;
  /** Dropdown chọn model cụ thể — chỉ panel LLM cần, Jev/Kev cố định 1 model. */
  modelSelect?: ReactNode;
}

/** TODO: gọi `POST /api/v1/model/...` và hiển thị answers/latency/usage thật — xem TODO.md. */
export function ModelPanel({ title, modelSelect }: ModelPanelProps) {
  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">{title}</h3>
        {modelSelect}
      </div>
      <p className="text-sm text-neutral-500">
        TODO: gọi <code>POST /api/v1/model/...</code> — xem TODO.md.
      </p>
    </Card>
  );
}
