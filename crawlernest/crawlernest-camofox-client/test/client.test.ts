import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { CamofoxClient, CamofoxError } from '../src/index.js';

interface Call {
  url: URL;
  method: string;
  headers: Record<string, string>;
  body: Record<string, unknown> | null;
}

type Reply = { status: number; body: unknown } | Error | 'hang';

/** A fetch that answers from a script and records every call. */
function scriptedFetch(replies: Reply[]) {
  const calls: Call[] = [];
  const impl = (async (input: URL | string, init: RequestInit = {}) => {
    calls.push({
      url: new URL(String(input)),
      method: init.method ?? 'GET',
      headers: init.headers as Record<string, string>,
      body: init.body ? JSON.parse(String(init.body)) : null,
    });
    const reply = replies.shift();
    if (reply === undefined) throw new Error('unexpected extra request');
    if (reply === 'hang') {
      return new Promise((_, reject) => {
        init.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
      });
    }
    if (reply instanceof Error) throw reply;
    return new Response(JSON.stringify(reply.body), { status: reply.status });
  }) as typeof fetch;
  return { impl, calls };
}

function refused(): Error {
  return new TypeError('fetch failed', { cause: Object.assign(new Error('connect ECONNREFUSED'), { code: 'ECONNREFUSED' }) });
}

function client(replies: Reply[], extra: Partial<ConstructorParameters<typeof CamofoxClient>[0]> = {}) {
  const fetch = scriptedFetch(replies);
  const retries: number[] = [];
  const instance = new CamofoxClient({
    userId: 'crawler',
    fetch: fetch.impl,
    sleep: async () => undefined,
    onRetry: (info) => retries.push(info.attempt),
    ...extra,
  });
  return { instance, calls: fetch.calls, retries };
}

const unresponsive = { status: 503, body: { error: 'Tab unresponsive', code: 'tab_unresponsive', retryable: true, recovery: 'create_new_tab' } };
const expired = { status: 503, body: { error: 'Browser session expired', code: 'session_expired', retryable: true, recovery: 'retry' } };

describe('requests', () => {
  it('creates a tab with userId and sessionKey', async () => {
    const { instance, calls } = client([{ status: 200, body: { tabId: 't1', url: 'https://www.topuniversities.com/' } }]);
    const tab = await instance.createTab({ sessionKey: 'qs-2026', url: 'https://www.topuniversities.com/' });
    assert.equal(tab.tabId, 't1');
    assert.equal(calls[0].method, 'POST');
    assert.equal(calls[0].url.pathname, '/tabs');
    assert.deepEqual(calls[0].body, { userId: 'crawler', sessionKey: 'qs-2026', url: 'https://www.topuniversities.com/' });
  });

  it('asks for a screenshot only when told to', async () => {
    const { instance, calls } = client([
      { status: 200, body: { url: 'u', snapshot: '', refsCount: 0, truncated: false, totalChars: 0 } },
      { status: 200, body: { url: 'u', snapshot: '', refsCount: 0, truncated: false, totalChars: 0 } },
    ]);
    await instance.snapshot('t1', { includeScreenshot: true, offset: 74800 });
    await instance.snapshot('t1');
    assert.equal(calls[0].url.pathname, '/tabs/t1/snapshot');
    assert.equal(calls[0].url.searchParams.get('userId'), 'crawler');
    assert.equal(calls[0].url.searchParams.get('includeScreenshot'), 'true');
    assert.equal(calls[0].url.searchParams.get('offset'), '74800');
    assert.equal(calls[1].url.searchParams.has('includeScreenshot'), false);
  });

  it('sends click, type and macro navigation bodies', async () => {
    const { instance, calls } = client([
      { status: 200, body: { ok: true } },
      { status: 200, body: { ok: true } },
      { status: 200, body: { ok: true, tabId: 't1', url: 'https://www.google.com/search?q=x' } },
    ]);
    await instance.click('t1', 'e1');
    await instance.type('t1', { ref: 'e3' }, 'National Taiwan University', { submit: true });
    await instance.navigate('t1', { macro: '@google_search', query: 'QS 2026' });
    assert.deepEqual(calls[0].body, { userId: 'crawler', ref: 'e1' });
    assert.deepEqual(calls[1].body, { userId: 'crawler', ref: 'e3', text: 'National Taiwan University', submit: true });
    assert.deepEqual(calls[2].body, { userId: 'crawler', macro: '@google_search', query: 'QS 2026' });
  });

  it('sends the api key as a bearer token', async () => {
    const { instance, calls } = client([{ status: 200, body: { ok: true } }], { apiKey: 'secret' });
    await instance.closeTab('t1');
    assert.equal(calls[0].headers.authorization, 'Bearer secret');
    assert.equal(calls[0].method, 'DELETE');
  });
});

describe('retries', () => {
  it('retries a read twice, then succeeds', async () => {
    const ok = { status: 200, body: { url: 'u', snapshot: '', refsCount: 0, truncated: false, totalChars: 0 } };
    const { instance, calls, retries } = client([expired, { status: 502, body: { error: 'bad gateway' } }, ok]);
    await instance.snapshot('t1');
    assert.equal(calls.length, 3);
    assert.deepEqual(retries, [1, 2]);
  });

  it('gives up after two retries and reports three attempts', async () => {
    const { instance, calls } = client([expired, expired, expired, expired]);
    await assert.rejects(instance.snapshot('t1'), (error: CamofoxError) => {
      assert.equal(error.attempts, 3);
      assert.equal(error.code, 'session_expired');
      return true;
    });
    assert.equal(calls.length, 3);
  });

  it('retries a read that timed out', async () => {
    const ok = { status: 200, body: { url: 'u', snapshot: '', refsCount: 0, truncated: false, totalChars: 0 } };
    const { instance, calls } = client(['hang', ok], { timeoutMs: 10 });
    await instance.snapshot('t1');
    assert.equal(calls.length, 2);
  });

  it('does not repeat a click that timed out: it may already have landed', async () => {
    const { instance, calls } = client(['hang', { status: 200, body: { ok: true } }], { timeoutMs: 10 });
    await assert.rejects(instance.click('t1', 'e1'), (error: CamofoxError) => error.kind === 'timeout');
    assert.equal(calls.length, 1);
  });

  it('repeats a click whose connection was refused', async () => {
    const { instance, calls } = client([refused(), { status: 200, body: { ok: true } }]);
    await instance.click('t1', 'e1');
    assert.equal(calls.length, 2);
  });

  it('does not retry a tab the server has destroyed', async () => {
    const { instance, calls } = client([unresponsive, unresponsive]);
    await assert.rejects(instance.snapshot('t1'), (error: CamofoxError) => error.needsNewTab);
    assert.equal(calls.length, 1);
  });

  it('does not retry stale refs; the caller must snapshot again', async () => {
    const pageChanged = { status: 409, body: { error: 'Page changed', code: 'page_changed', recovery: 'snapshot_then_retry' } };
    const { instance, calls } = client([pageChanged, pageChanged]);
    await assert.rejects(instance.click('t1', 'e9'), (error: CamofoxError) => error.needsFreshSnapshot);
    assert.equal(calls.length, 1);
  });

  it('treats closing an unknown tab as closed', async () => {
    const { instance } = client([{ status: 404, body: { error: 'Tab not found' } }]);
    assert.deepEqual(await instance.closeTab('t1'), { ok: true, alreadyClosed: true });
  });

  it('closes the tab when the work throws', async () => {
    const { instance, calls } = client([{ status: 200, body: { tabId: 't7', url: 'u' } }, { status: 200, body: { ok: true } }]);
    await assert.rejects(instance.withTab({ sessionKey: 's' }, async () => {
      throw new Error('boom');
    }), /boom/);
    assert.equal(calls[1].method, 'DELETE');
    assert.equal(calls[1].url.pathname, '/tabs/t7');
  });
});
