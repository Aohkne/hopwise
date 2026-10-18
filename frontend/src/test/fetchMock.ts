import { vi } from "vitest";

type Route = (url: string, init?: RequestInit) => unknown;

/** Stub fetch theo URL: trả JSON của route khớp đầu tiên, còn lại 404. */
export function mockFetchRoutes(routes: [RegExp, Route][]) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    for (const [pattern, handler] of routes) {
      if (pattern.test(url)) return new Response(JSON.stringify(handler(url, init)));
    }
    return new Response("not found", { status: 404 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}
