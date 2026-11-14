import { test, expect } from "@playwright/test";
import { request, forgetAuthentication } from "../src/lib/api";
const response = (status: number, data: unknown) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
test("concurrent expired requests share one refresh and replay once", async () => {
  const original = globalThis.fetch;
  forgetAuthentication();
  let renewed = false,
    rotations = 0,
    reads = 0;
  globalThis.fetch = async (input) => {
    const path = String(input);
    if (path.endsWith("/auth/csrf"))
      return response(200, { csrf_token: "test-nonce" });
    if (path.endsWith("/auth/refresh")) {
      rotations++;
      await new Promise((r) => setTimeout(r, 20));
      renewed = true;
      return response(200, { csrf_token: "test-nonce" });
    }
    if (path.endsWith("/auth/me"))
      return renewed
        ? response(200, { username: "operator" })
        : response(401, { error: { code: "ACCESS_EXPIRED" } });
    reads++;
    return renewed
      ? response(200, { ok: true })
      : response(401, { error: { code: "ACCESS_EXPIRED" } });
  };
  try {
    const results = await Promise.all([
      request("/stats"),
      request("/invoices"),
    ]);
    expect(results).toEqual([{ ok: true }, { ok: true }]);
    expect(rotations).toBe(1);
    expect(reads).toBe(4);
  } finally {
    globalThis.fetch = original;
    forgetAuthentication();
  }
});
test("financial failures are never retried on 500 or CSRF rejection", async () => {
  const original = globalThis.fetch;
  try {
    for (const status of [500, 403]) {
      forgetAuthentication();
      let posts = 0;
      globalThis.fetch = async (input, init) => {
        if (String(input).endsWith("/auth/csrf"))
          return response(200, { csrf_token: "nonce" });
        if (init?.method === "POST") posts++;
        return response(status, {
          error: {
            code: status === 403 ? "CSRF_REJECTED" : "FAILED",
            message: "failed",
          },
        });
      };
      await expect(
        request("/invoices/id/post", { method: "POST" }),
      ).rejects.toThrow();
      expect(posts).toBe(1);
    }
  } finally {
    globalThis.fetch = original;
    forgetAuthentication();
  }
});
