import "@testing-library/jest-dom/vitest";

// jsdom không có ResizeObserver — @xyflow/react dùng nó để theo dõi kích
// thước canvas. Polyfill tối thiểu, chỉ để test không crash.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
