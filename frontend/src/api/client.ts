/** Client gọi backend — không gọi Jev/Kev/LLM trực tiếp từ frontend
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

// TODO: callModel("jev" | "kev" | "llm", ...) — xem TODO.md, nối với
// backend POST /api/v1/model/jev|kev|llm khi làm tab Benchmark thật.
