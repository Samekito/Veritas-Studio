// Registers jest-dom matchers (toBeInTheDocument, etc.) on Vitest's expect.
import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom ships no media stack, so play()/pause() throw "Not implemented" and the
// error surfaces from React effect cleanup. Stub them at the boundary — media
// playback itself is verified in a real browser, not here.
Object.defineProperty(HTMLMediaElement.prototype, "play", {
  configurable: true,
  value: vi.fn().mockResolvedValue(undefined),
});
Object.defineProperty(HTMLMediaElement.prototype, "pause", {
  configurable: true,
  value: vi.fn(),
});
