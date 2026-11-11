import { NextResponse, type NextRequest } from "next/server";

/**
 * A per-client limit for the routes that make a model call: /api/agent/chat, /tasks and /explain.
 *
 * The Java API limits its own endpoints (clawer.security.RateLimits), but these three never pass through it:
 * chat calls the model from this server, and the other two go to the agent API on 8090, which bounds total
 * concurrency and body size but not how much one visitor may ask. Each request here can cost a model call, so one
 * address gets `CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE` of them a minute (default 30; 0 turns the limit off).
 *
 * Fixed window, in this process's memory, like the Java limiter: several web instances each count on their own,
 * and a restart forgets. The key is the right-most X-Forwarded-For hop -- the address the reverse proxy saw
 * (deploy/nginx/crawlernest.conf.example replaces the header) or, with no proxy, the socket address Next.js fills
 * in. Exposed directly with a client-written header, the key can be chosen by the client; see
 * docs/AUTH_LIMITATIONS.md.
 */

export type RateDecision = { allowed: boolean; retryAfterSeconds: number };

const SWEEP_THRESHOLD = 10_000;

export class FixedWindowLimiter {
  private readonly windows = new Map<string, { start: number; count: number }>();

  constructor(
    private readonly limit: number,
    private readonly windowMs: number,
    private readonly now: () => number = Date.now,
  ) {}

  /** Counts one request for `key` and says whether it is within the limit. */
  take(key: string): RateDecision {
    const now = this.now();
    const current = this.windows.get(key);
    const window = !current || now - current.start >= this.windowMs ? { start: now, count: 1 } : { start: current.start, count: current.count + 1 };
    this.windows.set(key, window);
    if (this.windows.size > SWEEP_THRESHOLD) {
      for (const [k, w] of this.windows) {
        if (now - w.start >= this.windowMs) this.windows.delete(k);
      }
    }
    if (window.count <= this.limit) return { allowed: true, retryAfterSeconds: 0 };
    return { allowed: false, retryAfterSeconds: Math.max(1, Math.ceil((window.start + this.windowMs - now) / 1000)) };
  }
}

/** The address to count a request against: the right-most forwarded hop, or one shared key when there is none. */
export function clientKey(forwardedFor: string | null): string {
  const hops = (forwardedFor ?? "").split(",").map((hop) => hop.trim()).filter(Boolean);
  return hops.length > 0 ? hops[hops.length - 1] : "unknown";
}

export function agentLimitPerMinute(env: Readonly<Record<string, string | undefined>> = process.env): number {
  const raw = env.CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE;
  if (raw === undefined || raw.trim() === "") return 30;
  const value = Number(raw);
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : 30;
}

// Kept on globalThis, not in a module variable: Next.js bundles each route separately, so a module-level limiter
// would be one per route and "30 a minute" would quietly become 30 for each of the three.
type AgentLimiterSlot = { limit: number; limiter: FixedWindowLimiter } | null;
const globalSlot = globalThis as typeof globalThis & { __crawlernestAgentLimiter?: AgentLimiterSlot };

/**
 * Null when the request may proceed; otherwise the 429 to return. Call it first in a model-calling route, before
 * the body is read.
 */
export function refuseIfOverAgentLimit(request: NextRequest): NextResponse | null {
  const limit = agentLimitPerMinute();
  if (limit === 0) return null;
  let slot = globalSlot.__crawlernestAgentLimiter ?? null;
  if (!slot || slot.limit !== limit) {
    slot = { limit, limiter: new FixedWindowLimiter(limit, 60_000) };
    globalSlot.__crawlernestAgentLimiter = slot;
  }
  const decision = slot.limiter.take(clientKey(request.headers.get("x-forwarded-for")));
  if (decision.allowed) return null;
  return NextResponse.json(
    { success: false, error: `Too many requests. Try again in ${decision.retryAfterSeconds} seconds.` },
    { status: 429, headers: { "Retry-After": String(decision.retryAfterSeconds), "Cache-Control": "no-store" } },
  );
}

/** For tests: forget every count. */
export function resetAgentLimiterForTests(): void {
  globalSlot.__crawlernestAgentLimiter = null;
}
