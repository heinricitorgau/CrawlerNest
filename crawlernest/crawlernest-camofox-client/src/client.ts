import { CamofoxError } from './errors.js';
import { DEFAULT_RETRY_POLICY, backoffDelay, isRetryable } from './retry.js';
import type {
  ActionResponse,
  CamofoxClientOptions,
  CamofoxErrorBody,
  ClickOptions,
  CloseTabResponse,
  CreateTabRequest,
  CreateTabResponse,
  ElementTarget,
  NavigateResponse,
  NavigateTarget,
  RetryInfo,
  RetryPolicy,
  SnapshotOptions,
  SnapshotResponse,
  TypeOptions,
} from './types.js';

export const DEFAULT_BASE_URL = 'http://localhost:9377';
const DEFAULT_TIMEOUT_MS = 60_000;

interface RequestSpec {
  method: 'GET' | 'POST' | 'DELETE';
  path: string;
  query?: Record<string, string | number | undefined>;
  body?: Record<string, unknown>;
  /** Safe to send twice; see isRetryable. */
  idempotent: boolean;
}

/** Thin, typed wrapper over the camofox-browser tab API. */
export class CamofoxClient {
  readonly baseUrl: string;
  readonly userId: string;
  private readonly apiKey: string | undefined;
  private readonly timeoutMs: number;
  private readonly retry: RetryPolicy;
  private readonly fetchImpl: typeof fetch;
  private readonly sleep: (ms: number) => Promise<void>;
  private readonly onRetry: ((info: RetryInfo) => void) | undefined;

  constructor(options: CamofoxClientOptions) {
    if (!options.userId) throw new TypeError('CamofoxClient: userId is required');
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, '');
    this.userId = options.userId;
    this.apiKey = options.apiKey;
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.retry = { ...DEFAULT_RETRY_POLICY, ...options.retry };
    this.fetchImpl = options.fetch ?? globalThis.fetch;
    this.sleep = options.sleep ?? ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
    this.onRetry = options.onRetry;
  }

  /** POST /tabs */
  createTab(request: CreateTabRequest): Promise<CreateTabResponse> {
    return this.request<CreateTabResponse>({
      method: 'POST',
      path: '/tabs',
      body: {
        userId: request.userId ?? this.userId,
        sessionKey: request.sessionKey,
        url: request.url,
        trace: request.trace,
      },
      idempotent: false,
    });
  }

  /** GET /tabs/:id/snapshot */
  snapshot(tabId: string, options: SnapshotOptions = {}): Promise<SnapshotResponse> {
    return this.request<SnapshotResponse>({
      method: 'GET',
      path: `/tabs/${encodeURIComponent(tabId)}/snapshot`,
      query: {
        userId: options.userId ?? this.userId,
        includeScreenshot: options.includeScreenshot ? 'true' : undefined,
        offset: options.offset,
      },
      idempotent: true,
    });
  }

  /** POST /tabs/:id/click */
  click(tabId: string, target: ElementTarget | string, options: ClickOptions = {}): Promise<ActionResponse> {
    return this.request<ActionResponse>({
      method: 'POST',
      path: `/tabs/${encodeURIComponent(tabId)}/click`,
      body: {
        userId: options.userId ?? this.userId,
        ...elementTarget(target),
        doubleClick: options.doubleClick,
      },
      idempotent: false,
    });
  }

  /** POST /tabs/:id/type */
  type(tabId: string, target: ElementTarget | string, text: string, options: TypeOptions = {}): Promise<ActionResponse> {
    return this.request<ActionResponse>({
      method: 'POST',
      path: `/tabs/${encodeURIComponent(tabId)}/type`,
      body: {
        userId: options.userId ?? this.userId,
        ...elementTarget(target),
        text,
        clear: options.clear,
        submit: options.submit,
      },
      // Clearing first makes a repeat land on the same field value; submitting does not.
      idempotent: Boolean(options.clear) && !options.submit,
    });
  }

  /** POST /tabs/:id/navigate -- a URL, or a search macro such as @google_search. */
  navigate(tabId: string, target: NavigateTarget | string, options: { userId?: string } = {}): Promise<NavigateResponse> {
    const destination = typeof target === 'string' ? { url: target } : target;
    return this.request<NavigateResponse>({
      method: 'POST',
      path: `/tabs/${encodeURIComponent(tabId)}/navigate`,
      body: { userId: options.userId ?? this.userId, ...destination },
      idempotent: true,
    });
  }

  /**
   * DELETE /tabs/:id. A tab the server no longer knows (404/410) counts as
   * closed, so a retry after a lost response does not fail.
   */
  async closeTab(tabId: string, options: { userId?: string } = {}): Promise<CloseTabResponse> {
    try {
      return await this.request<CloseTabResponse>({
        method: 'DELETE',
        path: `/tabs/${encodeURIComponent(tabId)}`,
        query: { userId: options.userId ?? this.userId },
        idempotent: true,
      });
    } catch (error) {
      if (error instanceof CamofoxError && (error.status === 404 || error.status === 410)) {
        return { ok: true, alreadyClosed: true };
      }
      throw error;
    }
  }

  /** Create a tab, run `work`, and close the tab even when `work` throws. */
  async withTab<T>(request: CreateTabRequest, work: (tabId: string, tab: CreateTabResponse) => Promise<T>): Promise<T> {
    const tab = await this.createTab(request);
    try {
      return await work(tab.tabId, tab);
    } finally {
      await this.closeTab(tab.tabId, { userId: request.userId }).catch(() => undefined);
    }
  }

  private async request<T>(spec: RequestSpec): Promise<T> {
    for (let attempt = 1; ; attempt += 1) {
      try {
        return await this.send<T>(spec);
      } catch (error) {
        const retriesUsed = attempt - 1;
        if (retriesUsed >= this.retry.maxRetries || !isRetryable(error, spec.idempotent)) {
          throw error instanceof CamofoxError ? error.withAttempts(attempt) : error;
        }
        const delayMs = backoffDelay(attempt, this.retry);
        this.onRetry?.({ method: spec.method, path: spec.path, attempt, delayMs, error: error as Error });
        await this.sleep(delayMs);
      }
    }
  }

  private async send<T>(spec: RequestSpec): Promise<T> {
    const url = new URL(this.baseUrl + spec.path);
    for (const [key, value] of Object.entries(spec.query ?? {})) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
    const headers: Record<string, string> = { accept: 'application/json' };
    if (spec.body) headers['content-type'] = 'application/json';
    if (this.apiKey) headers.authorization = `Bearer ${this.apiKey}`;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    const fail = (kind: CamofoxError['kind'], message: string, extra: Partial<ConstructorParameters<typeof CamofoxError>[0]> = {}) =>
      new CamofoxError({ kind, method: spec.method, path: spec.path, message, ...extra });

    let response: Response;
    let raw: string;
    try {
      response = await this.fetchImpl(url, {
        method: spec.method,
        headers,
        body: spec.body ? JSON.stringify(dropUndefined(spec.body)) : undefined,
        signal: controller.signal,
      });
      raw = await response.text();
    } catch (error) {
      if (controller.signal.aborted) throw fail('timeout', `no response within ${this.timeoutMs} ms`, { cause: error });
      throw fail('network', (error as Error).message ?? String(error), { cause: error });
    } finally {
      clearTimeout(timer);
    }

    let parsed: unknown = null;
    if (raw) {
      try {
        parsed = JSON.parse(raw);
      } catch {
        parsed = null;
      }
    }

    if (!response.ok) {
      const body = isErrorBody(parsed) ? parsed : { error: raw.slice(0, 500) || response.statusText };
      throw fail('http', `HTTP ${response.status}: ${body.error}`, { status: response.status, body });
    }
    if (parsed === null || typeof parsed !== 'object') {
      throw fail('protocol', `expected a JSON object, got ${JSON.stringify(raw.slice(0, 200))}`, { status: response.status });
    }
    return parsed as T;
  }
}

function elementTarget(target: ElementTarget | string): ElementTarget {
  return typeof target === 'string' ? { ref: target } : target;
}

function dropUndefined(body: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(body).filter(([, value]) => value !== undefined));
}

function isErrorBody(value: unknown): value is CamofoxErrorBody {
  return typeof value === 'object' && value !== null && typeof (value as { error?: unknown }).error === 'string';
}
