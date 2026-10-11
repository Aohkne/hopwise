/** Client gọi backend — không gọi Jev/Kev/LLM trực tiếp từ frontend
 * (API key phải ở server-side, xem skills/typesafe-ai/SKILL.md). */

const BASE_URL = "/api"; // proxy sang backend FastAPI, xem vite.config.ts

export async function getNode(nodeId: string) {
  const res = await fetch(`${BASE_URL}/graph/nodes/${nodeId}`);
  if (!res.ok) throw new Error(`getNode(${nodeId}) failed: ${res.status}`);
  return res.json();
}

export async function getNeighbors(nodeId: string) {
  const res = await fetch(`${BASE_URL}/graph/nodes/${nodeId}/neighbors`);
  if (!res.ok) throw new Error(`getNeighbors(${nodeId}) failed: ${res.status}`);
  return res.json();
}

// TODO: decide() và runBenchmark() — xem TODO.md, phụ thuộc
// backend/app/routers/decisions.py và benchmark.py (hiện trả 501).
