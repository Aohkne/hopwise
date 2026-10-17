/** Client gọi backend — không gọi Jev/LLM trực tiếp từ frontend
 * (API key phải ở server-side, xem skills/typesafe-ai/SKILL.md). */

const BASE_URL = "/api/v1"; // proxy /api sang backend FastAPI, xem vite.config.ts

export interface SearchResult {
  id: string;
  label: string;
  description: string | null;
}

export interface NodeDetail {
  id: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface Neighbor {
  edge_type: string;
  edge_props: Record<string, unknown>;
  target_id: string;
  target_label: string;
  target_description: string | null;
}

export interface GraphNode {
  id: string;
  label: string;
  caption: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: string;
}

export interface GraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export async function getDomainGraph(domain: string): Promise<GraphPayload> {
  const res = await fetch(`${BASE_URL}/graph/domains/${encodeURIComponent(domain)}`);
  if (!res.ok) throw new Error(`getDomainGraph(${domain}) failed: ${res.status}`);
  return res.json();
}

export async function searchNodes(q: string, limit = 20): Promise<SearchResult[]> {
  if (!q.trim()) return [];
  const res = await fetch(`${BASE_URL}/graph/search?q=${encodeURIComponent(q)}&limit=${limit}`);
  if (!res.ok) throw new Error(`searchNodes(${q}) failed: ${res.status}`);
  return res.json();
}

export async function getNode(nodeId: string): Promise<NodeDetail> {
  const res = await fetch(`${BASE_URL}/graph/nodes/${encodeURIComponent(nodeId)}`);
  if (!res.ok) throw new Error(`getNode(${nodeId}) failed: ${res.status}`);
  return res.json();
}

export async function getNeighbors(nodeId: string): Promise<Neighbor[]> {
  const res = await fetch(`${BASE_URL}/graph/nodes/${encodeURIComponent(nodeId)}/neighbors`);
  if (!res.ok) throw new Error(`getNeighbors(${nodeId}) failed: ${res.status}`);
  return res.json();
}

// ---- Benchmark --------------------------------------------------------

export type ModelKey = "jev" | "llm";
export type RunStatus = "running" | "found" | "not_found" | "timeout" | "stopped" | "error";

export interface TraceStep {
  step: number | null;
  phase: "domain" | "label" | "pick" | "visit" | string;
  decision?: string | null;
  node_id?: string | null;
  node_label?: string | null;
  node_caption?: string | null;
  from_node_id?: string | null;
  via_edge?: string | null;
  answer_score?: number | null;
  latency_ms: number | null;
  tokens: number | null;
  cost: number | null;
  candidates?: number | null;
}

export interface ModelResult {
  model: ModelKey;
  model_name: string;
  /** Phiên bản thật model đã trả lời, VD "typesafe/jev-1.13-20260917". */
  model_version?: string | null;
  status: RunStatus;
  answer_node_id: string | null;
  answer_text: string | null;
  error: string | null;
  elapsed_ms: number;
  tokens: number;
  cost: number;
  domain: string | null;
  label: string | null;
  steps?: TraceStep[];
  calls?: number;
}

export interface BenchmarkRun {
  id: string;
  question: string;
  started_at: string;
  status?: "running" | "done";
  llm_model?: string;
  models: Record<ModelKey, ModelResult>;
}

async function json<T>(res: Response, what: string): Promise<T> {
  if (!res.ok) throw new Error(`${what} failed: ${res.status}`);
  return res.json();
}

export interface ModelsInfo {
  /** LLM bật trong BASELINE_MODELS. */
  llm: string[];
  /** Phiên bản Jev theo cấu hình (JEV_MODEL). */
  jev: string;
}

export async function listModels(): Promise<ModelsInfo> {
  return json(await fetch(`${BASE_URL}/benchmark/models`), "listModels");
}

export async function startRun(question: string, llmModel: string): Promise<BenchmarkRun> {
  const res = await fetch(`${BASE_URL}/benchmark/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, llm_model: llmModel }),
  });
  return json(res, "startRun");
}

export async function getRun(runId: string): Promise<BenchmarkRun> {
  return json(await fetch(`${BASE_URL}/benchmark/runs/${encodeURIComponent(runId)}`), "getRun");
}

export async function stopRun(runId: string): Promise<void> {
  await json(
    await fetch(`${BASE_URL}/benchmark/runs/${encodeURIComponent(runId)}/stop`, { method: "POST" }),
    "stopRun"
  );
}

export async function listHistory(): Promise<BenchmarkRun[]> {
  return json(await fetch(`${BASE_URL}/benchmark/history`), "listHistory");
}
