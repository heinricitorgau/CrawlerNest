import { CamofoxError } from './errors.js';
import type { RetryPolicy } from './types.js';

export const DEFAULT_RETRY_POLICY: RetryPolicy = {
  maxRetries: 2,
  baseDelayMs: 500,
  maxDelayMs: 5_000,
};

/**
 * Whether a failed call may be sent again.
 *
 * A call that changes the page (click, type without clear, create tab) is only
 * repeated when the action cannot have happened: the connection was refused,
 * or the server answered 503 for a context that was torn down. After a
 * timeout or a 502/504 the click may already have landed, and clicking twice
 * is worse than failing once. Reads, navigation and close are repeated after
 * any transient failure.
 *
 * Never retried: 4xx (bad request, unknown or crashed tab, stale refs, tab
 * limit) and any error whose recovery is "create_new_tab" -- the same tab id
 * will fail the same way.
 */
export function isRetryable(error: unknown, idempotent: boolean): boolean {
  if (!(error instanceof CamofoxError)) return false;
  switch (error.kind) {
    case 'network':
      return idempotent || connectionRefused(error);
    case 'timeout':
      return idempotent;
    case 'protocol':
      return false;
    case 'http':
      if (error.recovery === 'create_new_tab') return false;
      if (error.status === 503) return true;
      if (error.status === 502 || error.status === 504) return idempotent;
      return false;
  }
}

function connectionRefused(error: CamofoxError): boolean {
  let cause: unknown = error.cause;
  for (let depth = 0; cause && depth < 4; depth += 1) {
    if ((cause as { code?: unknown }).code === 'ECONNREFUSED') return true;
    cause = (cause as { cause?: unknown }).cause;
  }
  return false;
}

/** Exponential backoff with full jitter: a random delay in [0, base * 2^(retry-1)], capped. */
export function backoffDelay(retry: number, policy: RetryPolicy, random: () => number = Math.random): number {
  const ceiling = Math.min(policy.maxDelayMs, policy.baseDelayMs * 2 ** (retry - 1));
  return Math.round(ceiling * random());
}
