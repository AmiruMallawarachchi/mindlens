/**
 * The hosted backend is a Render free instance, which sleeps after ~15
 * minutes of quiet and takes 30-60s to answer its next request. These cover
 * what the client does about that, and just as much what it must not do:
 * replay a write, or make a reader who is offline wait for a wake that is
 * never coming.
 *
 * Timers are fake throughout — the whole point of the code under test is how
 * long it waits, so the tests measure virtual time rather than burn a minute
 * of real it.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  getAccessToken,
  refreshAccessToken,
  request,
  setAccessToken,
} from "@/lib/api";

// Not exported by api.ts; the numbers here are the contract being tested.
const REQUEST_TIMEOUT_MS = 12_000;

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * A request that never answers on its own and rejects only when its signal is
 * aborted — which is what a connection Render is holding open while the
 * service starts looks like from the browser.
 */
function stillWaking(signal?: AbortSignal | null): Promise<Response> {
  return new Promise((_resolve, reject) => {
    signal?.addEventListener("abort", () => {
      reject(new DOMException("The operation was aborted.", "AbortError"));
    });
  });
}

type Behaviour = (url: string, init?: RequestInit) => Promise<Response>;

function stubFetch(behaviour: Behaviour): string[] {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string, init?: RequestInit) => {
      calls.push(input);
      return behaviour(input, init);
    }),
  );
  return calls;
}

const of = (calls: string[], suffix: string) =>
  calls.filter((url) => url.endsWith(suffix));

describe("cold start retry", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setAccessToken("token");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("replays a read once the backend answers the wake probe", async () => {
    let first = true;
    const calls = stubFetch(async (url, init) => {
      if (url.endsWith("/ready")) return response({ status: "ok" });
      if (first) {
        first = false;
        return stillWaking(init?.signal);
      }
      return response([{ id: "session-1" }]);
    });

    // Started before the clock moves, so the rejection of a failing case is
    // never momentarily unhandled while the timers run.
    const settled = expect(
      request<{ id: string }[]>("/api/v1/sessions"),
    ).resolves.toEqual([{ id: "session-1" }]);
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS + 500);
    await settled;

    expect(of(calls, "/api/v1/sessions")).toHaveLength(2);
    expect(of(calls, "/ready").length).toBeGreaterThan(0);
  });

  it("probes first, so a write that could duplicate is never replayed", async () => {
    const calls = stubFetch(async (url, init) => {
      if (url.endsWith("/ready")) return response({ status: "ok" });
      return stillWaking(init?.signal);
    });

    const settled = expect(
      request("/api/v1/journal", {
        method: "POST",
        body: JSON.stringify({ content: "first entry" }),
      }),
    ).rejects.toThrow(/taking too long/);
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS + 5_000);
    await settled;

    expect(of(calls, "/api/v1/journal")).toHaveLength(1);
    // No replay, so no reason to have asked the backend anything.
    expect(of(calls, "/ready")).toHaveLength(0);
  });

  it("gives up inside the wake budget when nothing ever answers", async () => {
    const startedAt = Date.now();
    let elapsedMs = 0;
    let failure: ApiError | null = null;
    const calls = stubFetch((_url, init) => stillWaking(init?.signal));

    const pending = request("/api/v1/sessions").catch((error: ApiError) => {
      elapsedMs = Date.now() - startedAt;
      failure = error;
      throw error;
    });
    const settled = expect(pending).rejects.toBeInstanceOf(ApiError);
    await vi.advanceTimersByTimeAsync(120_000);
    await settled;

    expect(failure!.message).toMatch(/taking too long/);
    expect(failure!.status).toBe(0);
    expect(of(calls, "/api/v1/sessions")).toHaveLength(1);
    // Waited for the wake, then stopped waiting: the status-0 error above is
    // the whole answer, not another attempt or another minute of silence.
    expect(elapsedMs).toBeGreaterThanOrEqual(45_000);
    expect(elapsedMs).toBeLessThan(70_000);
    expect(of(calls, "/ready").length).toBeLessThan(10);
  });

  it("fails at once on a refused connection — a backend that was never started", async () => {
    const calls = stubFetch(async () => {
      throw new TypeError("Failed to fetch");
    });

    await expect(request("/api/v1/sessions")).rejects.toThrow(
      /Couldn't reach MindLens/,
    );
    expect(of(calls, "/ready")).toHaveLength(0);
  });

  it("tells an offline reader to check their connection instead of waiting", async () => {
    vi.stubGlobal("navigator", { onLine: false });
    const calls = stubFetch((_url, init) => stillWaking(init?.signal));

    const settled = expect(request("/api/v1/sessions")).rejects.toThrow(
      /You're offline/,
    );
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS + 500);
    await settled;

    expect(of(calls, "/ready")).toHaveLength(0);
  });

  it("shares one wait between concurrent reads instead of a loop each", async () => {
    const seen = new Set<string>();
    let probes = 0;
    const calls = stubFetch(async (url, init) => {
      if (url.endsWith("/ready")) {
        probes += 1;
        // The instance answers the third time it is asked.
        return probes > 2 ? response({ status: "ok" }) : stillWaking(init?.signal);
      }
      if (!seen.has(url)) {
        seen.add(url);
        return stillWaking(init?.signal);
      }
      return response([{ id: "session-1" }]);
    });

    const settled = Promise.all([
      expect(request("/api/v1/sessions")).resolves.toEqual([{ id: "session-1" }]),
      expect(request("/api/v1/memory")).resolves.toEqual([{ id: "session-1" }]),
      expect(request("/api/v1/journal?limit=30")).resolves.toEqual([
        { id: "session-1" },
      ]),
    ]);
    await vi.advanceTimersByTimeAsync(60_000);
    await settled;

    // Three asks for the wake, not three per waiting request.
    expect(of(calls, "/ready")).toHaveLength(3);
  });

  it("keeps a session alive when the refresh itself hits the wake", async () => {
    setAccessToken(null);
    let refreshes = 0;
    stubFetch(async (url, init) => {
      if (url.endsWith("/ready")) return response({ status: "ok" });
      if (url.endsWith("/api/v1/auth/refresh")) {
        refreshes += 1;
        // The first attempt is lost to the cold start; the second succeeds.
        return refreshes === 1
          ? stillWaking(init?.signal)
          : response({ access_token: "fresh-token" });
      }
      return stillWaking(init?.signal);
    });

    const pending = refreshAccessToken();
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS + 500);

    await expect(pending).resolves.toBe(true);
    expect(refreshes).toBe(2);
    expect(getAccessToken()).toBe("fresh-token");
  });

  it("still reports a refused refresh as signed out", async () => {
    stubFetch(async (url) => {
      if (url.endsWith("/api/v1/auth/refresh")) {
        return response({ detail: "Invalid refresh token" }, 401);
      }
      return response({ status: "ok" });
    });

    await expect(refreshAccessToken()).resolves.toBe(false);
  });
});
