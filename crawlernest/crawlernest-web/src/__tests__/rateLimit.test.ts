/**
 * @jest-environment node
 */
import { NextRequest } from "next/server";

import { POST as chat } from "@/app/api/agent/chat/route";
import { POST as explain } from "@/app/api/agent/explain/route";
import { POST as tasks } from "@/app/api/agent/tasks/route";
import { FixedWindowLimiter, agentLimitPerMinute, clientKey, resetAgentLimiterForTests } from "@/lib/rateLimit";

const originalFetch = global.fetch;
const originalLimit = process.env.CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE;

function post(path: string, forwardedFor: string | null, body: unknown = { message: "hello" }): NextRequest {
  return new NextRequest(`http://localhost:3000${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(forwardedFor ? { "x-forwarded-for": forwardedFor } : {}) },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  resetAgentLimiterForTests();
  global.fetch = jest.fn(async () => ({
    ok: true, status: 200, headers: new Headers({ "content-type": "application/json" }),
    text: async () => JSON.stringify({ success: true, data: {} }),
    json: async () => ({ success: true, data: {} }),
  })) as unknown as typeof fetch;
});

afterEach(() => {
  global.fetch = originalFetch;
  if (originalLimit === undefined) delete process.env.CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE;
  else process.env.CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE = originalLimit;
});

describe("FixedWindowLimiter", () => {
  it("allows the limit, refuses the next with the seconds left, and starts again when the window ends", () => {
    let now = 1_000_000;
    const limiter = new FixedWindowLimiter(2, 60_000, () => now);
    expect(limiter.take("a").allowed).toBe(true);
    expect(limiter.take("a").allowed).toBe(true);
    now += 15_000;
    expect(limiter.take("a")).toEqual({ allowed: false, retryAfterSeconds: 45 });
    expect(limiter.take("b").allowed).toBe(true); // another client has its own count
    now += 45_000;
    expect(limiter.take("a").allowed).toBe(true);
  });
});

describe("clientKey and the configured limit", () => {
  it("counts by the right-most forwarded hop, which is the one the proxy wrote", () => {
    expect(clientKey("1.2.3.4, 198.51.100.7")).toBe("198.51.100.7");
    expect(clientKey(" 203.0.113.9 ")).toBe("203.0.113.9");
    expect(clientKey(null)).toBe("unknown");
  });

  it("defaults to 30 a minute, takes a number, and ignores junk", () => {
    expect(agentLimitPerMinute({})).toBe(30);
    expect(agentLimitPerMinute({ CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE: "5" })).toBe(5);
    expect(agentLimitPerMinute({ CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE: "0" })).toBe(0);
    expect(agentLimitPerMinute({ CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE: "lots" })).toBe(30);
  });
});

describe("the model-calling routes share one limit per client", () => {
  it("answers 429 with Retry-After once a client is over it, on all three routes, without calling upstream", async () => {
    process.env.CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE = "3";
    const client = "198.51.100.20";
    expect((await tasks(post("/api/agent/tasks", client))).status).toBe(200);
    expect((await explain(post("/api/agent/explain", client))).status).toBe(200);
    expect((await chat(post("/api/agent/chat", client))).status).toBe(200);
    const upstreamCalls = (global.fetch as jest.Mock).mock.calls.length;

    for (const [route, path] of [[tasks, "/api/agent/tasks"], [explain, "/api/agent/explain"], [chat, "/api/agent/chat"]] as const) {
      const refused = await route(post(path, client));
      expect(refused.status).toBe(429);
      expect(Number(refused.headers.get("Retry-After"))).toBeGreaterThan(0);
      expect((await refused.json()).success).toBe(false);
    }
    expect((global.fetch as jest.Mock).mock.calls.length).toBe(upstreamCalls);

    // Someone else is unaffected.
    expect((await tasks(post("/api/agent/tasks", "198.51.100.21"))).status).toBe(200);
  });

  it("is off when the limit is 0", async () => {
    process.env.CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE = "0";
    for (let i = 0; i < 40; i++) {
      expect((await tasks(post("/api/agent/tasks", "198.51.100.30"))).status).toBe(200);
    }
  });
});
