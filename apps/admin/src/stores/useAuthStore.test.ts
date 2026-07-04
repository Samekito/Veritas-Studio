import { beforeEach, describe, expect, it, vi } from "vitest";

// Stub the network login so the store test stays offline.
vi.mock("@veritas/shared", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@veritas/shared")>();
  return {
    ...actual,
    api: { ...actual.api, adminLogin: vi.fn(async () => ({ token: "tok-123" })) },
  };
});

import { useAuthStore } from "./useAuthStore";

describe("useAuthStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.setState({ token: null });
  });

  it("login stores the token in state and localStorage (main path)", async () => {
    await useAuthStore.getState().login("pw");
    expect(useAuthStore.getState().token).toBe("tok-123");
    expect(localStorage.getItem("veritas_admin_token")).toBe("tok-123");
  });

  it("logout clears the token from state and localStorage (reset path)", () => {
    useAuthStore.setState({ token: "tok-123" });
    localStorage.setItem("veritas_admin_token", "tok-123");
    useAuthStore.getState().logout();
    expect(useAuthStore.getState().token).toBeNull();
    expect(localStorage.getItem("veritas_admin_token")).toBeNull();
  });
});
