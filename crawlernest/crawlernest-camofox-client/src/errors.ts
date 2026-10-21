import type { CamofoxErrorBody, CamofoxRecovery } from './types.js';

export type CamofoxErrorKind =
  /** The server answered with a non-2xx status. */
  | 'http'
  /** No response: connection refused, reset, DNS failure. */
  | 'network'
  /** No response within timeoutMs. */
  | 'timeout'
  /** A 2xx response whose body was not the JSON we expected. */
  | 'protocol';

export class CamofoxError extends Error {
  readonly kind: CamofoxErrorKind;
  readonly method: string;
  readonly path: string;
  readonly status: number | null;
  /** Server error code, e.g. "page_changed", "tab_unresponsive", "session_expired". */
  readonly code: string | null;
  readonly recovery: CamofoxRecovery | string | null;
  readonly body: CamofoxErrorBody | null;
  readonly attempts: number;

  constructor(init: {
    kind: CamofoxErrorKind;
    method: string;
    path: string;
    message: string;
    status?: number | null;
    body?: CamofoxErrorBody | null;
    attempts?: number;
    cause?: unknown;
  }) {
    super(`${init.method} ${init.path}: ${init.message}`, { cause: init.cause });
    this.name = 'CamofoxError';
    this.kind = init.kind;
    this.method = init.method;
    this.path = init.path;
    this.status = init.status ?? null;
    this.body = init.body ?? null;
    this.code = this.body?.code ?? null;
    this.recovery = this.body?.recovery ?? null;
    this.attempts = init.attempts ?? 1;
  }

  withAttempts(attempts: number): CamofoxError {
    return new CamofoxError({
      kind: this.kind,
      method: this.method,
      path: this.path,
      message: this.message.slice(`${this.method} ${this.path}: `.length),
      status: this.status,
      body: this.body,
      attempts,
      cause: this.cause,
    });
  }

  /** The tab is gone (crashed, reaped, unresponsive): open a new one rather than retry. */
  get needsNewTab(): boolean {
    return this.recovery === 'create_new_tab' || this.status === 404 || this.status === 410;
  }

  /** The refs are stale: take a fresh snapshot and look the element up again. */
  get needsFreshSnapshot(): boolean {
    return this.recovery === 'snapshot_then_retry' || this.code === 'page_changed';
  }
}
