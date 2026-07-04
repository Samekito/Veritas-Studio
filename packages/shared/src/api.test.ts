import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, setAdminToken } from "./index";

// Build a minimal fake Response for the api client's `j<T>()` helper
function fakeFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: "status " + status,
    json: async () => body,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
  });
}

describe("shared api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setAdminToken(null);
  });

  it("returns parsed JSON on a 2xx response (main path)", async () => {
    vi.stubGlobal("fetch", fakeFetch(200, { ok: true, missing_keys: [] }));
    await expect(api.health()).resolves.toMatchObject({ ok: true });
  });

  it("throws ApiError carrying the HTTP status on failure (failure path)", async () => {
    vi.stubGlobal("fetch", fakeFetch(401, "Admin authentication required"));
    await expect(api.adminOverview()).rejects.toBeInstanceOf(ApiError);
    vi.stubGlobal("fetch", fakeFetch(503, "down"));
    await expect(api.stats()).rejects.toMatchObject({ status: 503 });
  });

  it("injects the X-Admin-Token header only after setAdminToken (edge)", async () => {
    const f = fakeFetch(200, {});
    vi.stubGlobal("fetch", f);
    await api.adminOverview(); // no token yet
    expect((f.mock.calls[0][1] as RequestInit).headers).toEqual({});

    setAdminToken("secret-token");
    await api.adminOverview();
    expect((f.mock.calls[1][1] as RequestInit).headers).toMatchObject({
      "X-Admin-Token": "secret-token",
    });
  });
});
