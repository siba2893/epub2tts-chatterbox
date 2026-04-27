import "@testing-library/jest-dom/vitest";

// Stub EventSource so SSE-driven components don't blow up in jsdom.
class StubEventSource {
  url: string;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onopen: ((e: Event) => void) | null = null;
  readyState = 0;
  constructor(url: string) {
    this.url = url;
  }
  close() {
    /* no-op */
  }
  addEventListener() {
    /* no-op */
  }
  removeEventListener() {
    /* no-op */
  }
  dispatchEvent() {
    return true;
  }
}
(globalThis as { EventSource?: unknown }).EventSource = StubEventSource;
