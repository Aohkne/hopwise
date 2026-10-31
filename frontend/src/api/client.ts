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
  /** "out" nếu cạnh đi ra từ node này, "in" nếu đi vào. */
  direction: "out" | "in";
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
  // 404 = domain chưa có dữ liệu (VD chưa upload tài liệu nào): coi là graph rỗng, không phải lỗi.
  if (res.status === 404) return { nodes: [], edges: [] };
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

// ---- Upload tài liệu (bản 2.0.0) ---------------------------------------

export interface DocumentReport {
  entities: number;
  relationships: number;
  claims: number;
  chunks: number;
  domain: string;
  /** Record model trả sai định dạng nên bị bỏ, và chunk bị lỗi. */
  skipped: string[];
  errors: string[];
}

export interface DocumentJob {
  id: string;
  name: string;
  domain: string;
  status: "running" | "done" | "error";
  done_chunks: number;
  total_chunks: number;
  report: DocumentReport | null;
  error: string | null;
}

/** Gửi văn bản để LLM trích xuất Entity / Relationship / Claim vào graph; trả job chạy nền. */
export async function uploadDocument(name: string, text: string, domain?: string): Promise<DocumentJob> {
  const res = await fetch(`${BASE_URL}/graph/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, text, ...(domain ? { domain } : {}) }),
  });
  if (!res.ok) {
    // 422 mang lý do cụ thể (văn bản trống / quá dài / domain sai) — cho người dùng thấy.
    const detail = await res.json().then((b: { detail?: unknown }) => b.detail, () => null);
    throw new Error(typeof detail === "string" ? detail : `uploadDocument failed: ${res.status}`);
  }
  return res.json();
}

export async function getDocumentJob(jobId: string): Promise<DocumentJob> {
  const res = await fetch(`${BASE_URL}/graph/documents/${encodeURIComponent(jobId)}`);
  if (!res.ok) throw new Error(`getDocumentJob(${jobId}) failed: ${res.status}`);
  return res.json();
}

// ---- Benchmark --------------------------------------------------------

export type ModelKey = "jev" | "ollama" | "nvidia";
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
  /** So với ground truth: true/false khi model tìm ra đáp án; null = không chấm. */
  correct?: boolean | null;
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
  /** Câu ground truth (nếu chạy từ bộ câu hỏi mẫu) và các node đáp án đúng. */
  case_id?: string | null;
  expected_answers?: string[] | null;
  models: Record<ModelKey, ModelResult>;
}

async function json<T>(res: Response, what: string): Promise<T> {
  if (!res.ok) throw new Error(`${what} failed: ${res.status}`);
  return res.json();
}

export interface ModelsInfo {
  /** Phiên bản Jev theo cấu hình (JEV_MODEL). */
  jev: string;
  /** Gemma chạy local bằng Ollama (OLLAMA_MODEL); version = null nếu Ollama chưa bật / chưa pull. */
  ollama: { model: string | null; version: string | null };
  /** gpt-oss qua NVIDIA NIM (NVIDIA_MODEL). */
  nvidia: { model: string | null };
}

export interface CaseSummary {
  id: string;
  domain: string;
  question: string;
  hops: number;
}

export async function listCases(): Promise<CaseSummary[]> {
  return json(await fetch(`${BASE_URL}/benchmark/cases`), "listCases");
}

export async function listModels(): Promise<ModelsInfo> {
  return json(await fetch(`${BASE_URL}/benchmark/models`), "listModels");
}

export async function startRun(question: string, caseId?: string | null): Promise<BenchmarkRun> {
  const res = await fetch(`${BASE_URL}/benchmark/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, ...(caseId ? { case_id: caseId } : {}) }),
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
