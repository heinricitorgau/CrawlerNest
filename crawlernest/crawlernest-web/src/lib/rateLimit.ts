import { NextResponse, type NextRequest } from "next/server";

/**
 * A per-client limit for the routes that make a model call: /api/agent/chat, /tasks and /explain.
 *
 * The Java API limits its own endpoints (clawer.security.RateLimits), but these three never pass through it:
 * chat calls the model from this server, and the other two go to the agent API on 8090, which bounds total
 * concurrency and body size but not how much one visitor may ask. Each request here can cost a model call, so one
 * address gets `CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE` of them a minute (default 30) and
 * `CRAWLERNEST_AGENT_RATE_LIMIT_PER_DAY` a day (default 500); 0 turns either off.
 *
 * Sliding windows, in this process's memory: several web instances each count on their own,
 * and a restart forgets. The key is the right-most X-Forwarded-For hop -- the address the reverse proxy saw
 * (deploy/nginx/crawlernest.conf.example replaces the header) or, with no proxy, the socket address Next.js fills
 * in. Exposed directly with a client-written header, the key can be chosen by the client; see
 * docs/AUTH_LIMITATIONS.md.
 */

export type RateDecision = { allowed: boolean; retryAfterSeconds: number };

const SWEEP_THRESHOLD = 10_000;

/**
 * At most `limit` requests per key in any stretch of `windowMs`: each request's time is kept until it is older than
 * the window. A fixed window resets on a boundary, so a client could spend the limit just before it and again just
 * after -- twice the limit in seconds -- which matters when each request is a model call. A refused request is not
 * recorded, so being refused never pushes the next allowed moment back. Memory is one timestamp per request still
 * in the window, at most `limit` per key.
 */
export class SlidingWindowLimiter {
  private readonly hits = new Map<string, number[]>();

  constructor(
    private readonly limit: number,
    private readonly windowMs: number,
    private readonly now: () => number = Date.now,
  ) {}

  private live(key: string, now: number): number[] {
    const times = this.hits.get(key) ?? [];
    let drop = 0;
    while (drop < times.length && now - times[drop] >= this.windowMs) drop++;
    return drop > 0 ? times.slice(drop) : times;
  }

  /** Whether one more request would fit for `key` now, without recording it. */
  check(key: string): RateDecision {
    const now = this.now();
    const times = this.live(key, now);
    if (times.length < this.limit) return { allowed: true, retryAfterSeconds: 0 };
    // It fits again when the oldest request still counted leaves the window.
    return { allowed: false, retryAfterSeconds: Math.max(1, Math.ceil((times[0] + this.windowMs - now) / 1000)) };
  }

  /** Records one request for `key` if it fits; otherwise records nothing and says how long to wait. */
  take(key: string): RateDecision {
    const now = this.now();
    const times = this.live(key, now);
    const decision: RateDecision =
      times.length < this.limit
        ? { allowed: true, retryAfterSeconds: 0 }
        : { allowed: false, retryAfterSeconds: Math.max(1, Math.ceil((times[0] + this.windowMs - now) / 1000)) };
    if (decision.allowed) times.push(now);
    if (times.length > 0) this.hits.set(key, times);
    else this.hits.delete(key);
    if (this.hits.size > SWEEP_THRESHOLD) {
      for (const [k, t] of this.hits) {
        if (t.length === 0 || now - t[t.length - 1] >= this.windowMs) this.hits.delete(k);
      }
    }
    return decision;
  }
}

/** The address to count a request against: the right-most forwarded hop, or one shared key when there is none. */
export function clientKey(forwardedFor: string | null): string {
  const hops = (forwardedFor ?? "").split(",").map((hop) => hop.trim()).filter(Boolean);
  return hops.length > 0 ? hops[hops.length - 1] : "unknown";
}

type Env = Readonly<Record<string, string | undefined>>;

function limitFrom(raw: string | undefined, fallback: number): number {
  if (raw === undefined || raw.trim() === "") return fallback;
  const value = Number(raw);
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : fallback;
}

export function agentLimitPerMinute(env: Env = process.env): number {
  return limitFrom(env.CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE, 30);
}

/** A day's budget per client address, so a patient client cannot spend 30 a minute all day (43,200). 0 = off. */
export function agentLimitPerDay(env: Env = process.env): number {
  return limitFrom(env.CRAWLERNEST_AGENT_RATE_LIMIT_PER_DAY, 500);
}

// Kept on globalThis, not in a module variable: Next.js bundles each route separately, so a module-level limiter
// would be one per route and "30 a minute" would quietly become 30 for each of the three.
type AgentLimiters = { perMinute: number; perDay: number; minute: SlidingWindowLimiter | null; day: SlidingWindowLimiter | null };
const globalSlot = globalThis as typeof globalThis & { __crawlernestAgentLimiter?: AgentLimiters | null };

/**
 * Null when the request may proceed; otherwise the 429 to return. Call it first in a model-calling route, before
 * the body is read. Both budgets are checked before either is charged, so a request refused by one costs nothing
 * in the other.
 */
export function refuseIfOverAgentLimit(request: NextRequest): NextResponse | null {
  const perMinute = agentLimitPerMinute();
  const perDay = agentLimitPerDay();
  let slot = globalSlot.__crawlernestAgentLimiter ?? null;
  if (!slot || slot.perMinute !== perMinute || slot.perDay !== perDay) {
    slot = {
      perMinute,
      perDay,
      minute: perMinute > 0 ? new SlidingWindowLimiter(perMinute, 60_000) : null,
      day: perDay > 0 ? new SlidingWindowLimiter(perDay, 86_400_000) : null,
    };
    globalSlot.__crawlernestAgentLimiter = slot;
  }
  const key = clientKey(request.headers.get("x-forwarded-for"));
  const refusal = [slot.minute, slot.day].map((limiter) => limiter?.check(key)).find((d) => d && !d.allowed);
  if (!refusal) {
    slot.minute?.take(key);
    slot.day?.take(key);
    return null;
  }
  return NextResponse.json(
    { success: false, error: `Too many requests. Try again in ${refusal.retryAfterSeconds} seconds.` },
    { status: 429, headers: { "Retry-After": String(refusal.retryAfterSeconds), "Cache-Control": "no-store" } },
  );
}

/** For tests: forget every count. */
export function resetAgentLimiterForTests(): void {
  globalSlot.__crawlernestAgentLimiter = null;
}
