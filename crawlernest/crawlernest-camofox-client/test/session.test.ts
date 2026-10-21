import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { describe, it } from 'node:test';

import { CamofoxClient, initSession, parseNetscapeCookies, saveTraces } from '../src/index.js';
import type { CamofoxCookie } from '../src/index.js';

const NOW = new Date('2026-10-21T00:00:00Z');
const FUTURE = Math.floor(Date.UTC(2027, 0, 1) / 1000);
const PAST = Math.floor(Date.UTC(2025, 0, 1) / 1000);

interface Call {
  method: string;
  path: string;
  auth: string | undefined;
  body: unknown;
}

/** A fake camofox-browser that routes by method and path. */
function fakeServer(routes: Record<string, (body: unknown) => Response>) {
  const calls: Call[] = [];
  const fetch = (async (input: URL | string, init: RequestInit = {}) => {
    const url = new URL(String(input));
    const key = `${init.method ?? 'GET'} ${url.pathname}`;
    const body = init.body ? JSON.parse(String(init.body)) : null;
    calls.push({ method: init.method ?? 'GET', path: url.pathname, auth: (init.headers as Record<string, string>).authorization, body });
    const handler = routes[key];
    return handler ? handler(body) : new Response(JSON.stringify({ error: `no route ${key}` }), { status: 404 });
  }) as typeof globalThis.fetch;
  return { fetch, calls };
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe('parseNetscapeCookies', () => {
  const file = [
    '﻿# Netscape HTTP Cookie File',
    '',
    `.example.com\tTRUE\t/\tTRUE\t${FUTURE}\tsid\tabc`,
    `#HttpOnly_.example.com\tTRUE\t/account\tFALSE\t0\ttoken\tx\ty`,
    `.example.com\tTRUE\t/\tFALSE\t${PAST}\told\tgone`,
    'not a cookie line',
  ].join('\r\n');
  const { cookies, skipped } = parseNetscapeCookies(file, NOW);

  it('reads cookies, HttpOnly lines and session cookies', () => {
    assert.deepEqual(cookies, [
      { name: 'sid', value: 'abc', domain: '.example.com', path: '/', expires: FUTURE, httpOnly: false, secure: true },
      // Expiry 0 is a session cookie: -1 for Playwright, not 1970. A tab inside the value survives.
      { name: 'token', value: 'x\ty', domain: '.example.com', path: '/account', expires: -1, httpOnly: true, secure: false },
    ]);
  });

  it('reports expired and malformed lines instead of dropping them silently', () => {
    assert.deepEqual(skipped.map((s) => s.line), [5, 6]);
    assert.match(skipped[0].reason, /old for \.example\.com expired 2025-01-01/);
    assert.match(skipped[1].reason, /expected 7 tab-separated fields/);
  });
});

describe('cookie import', () => {
  it('sends the API key, not the access key, and batches by 500', async () => {
    const server = fakeServer({
      'POST /sessions/crawler/cookies': (body) => json({ ok: true, userId: 'crawler', count: (body as { cookies: unknown[] }).cookies.length }),
    });
    const client = new CamofoxClient({ userId: 'crawler', accessKey: 'access', apiKey: 'api', fetch: server.fetch });
    const cookies: CamofoxCookie[] = Array.from({ length: 1001 }, (_, i) => ({ name: `c${i}`, value: 'v', domain: '.example.com' }));

    const result = await client.importCookies(cookies);

    assert.deepEqual(result, { ok: true, userId: 'crawler', count: 1001, batches: 3 });
    assert.deepEqual(server.calls.map((c) => (c.body as { cookies: unknown[] }).cookies.length), [500, 500, 1]);
    assert.ok(server.calls.every((c) => c.auth === 'Bearer api'));
  });

  it('sends the access key on ordinary routes', async () => {
    const server = fakeServer({ 'GET /health': () => json({ ok: true }) });
    await new CamofoxClient({ userId: 'u', accessKey: 'access', apiKey: 'api', fetch: server.fetch }).health();
    assert.equal(server.calls[0].auth, 'Bearer access');
  });

  it('imports every file, then opens a traced first tab', async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), 'camofox-cookies-'));
    try {
      const file = path.join(dir, 'target.txt');
      await writeFile(file, `.example.com\tTRUE\t/\tFALSE\t0\tsid\tabc\n`);
      const server = fakeServer({
        'GET /health': () => json({ ok: true }),
        'POST /sessions/u/cookies': () => json({ ok: true, userId: 'u', count: 1 }),
        'POST /tabs': () => json({ tabId: 't1', url: 'https://example.com/' }),
      });
      const client = new CamofoxClient({ userId: 'u', fetch: server.fetch });

      const result = await initSession(client, {
        cookieFiles: [file],
        firstTab: { sessionKey: 'k', url: 'https://example.com/', trace: true },
      });

      assert.deepEqual(server.calls.map((c) => `${c.method} ${c.path}`), ['GET /health', 'POST /sessions/u/cookies', 'POST /tabs']);
      assert.deepEqual(server.calls[2].body, { userId: 'u', sessionKey: 'k', url: 'https://example.com/', trace: true });
      assert.equal(result.cookies[0].count, 1);
      assert.equal(result.tab?.tabId, 't1');
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it('refuses a cookie file with nothing usable in it', async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), 'camofox-cookies-'));
    try {
      const file = path.join(dir, 'empty.txt');
      await writeFile(file, '# Netscape HTTP Cookie File\n');
      const server = fakeServer({ 'GET /health': () => json({ ok: true }) });
      await assert.rejects(initSession(new CamofoxClient({ userId: 'u', fetch: server.fetch }), { cookieFiles: [file] }), /no usable cookies/);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe('saveTraces', () => {
  it('closes the session first, downloads each zip once, and ignores unsafe names', async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), 'camofox-traces-'));
    try {
      const zip = new Uint8Array([0x50, 0x4b, 0x03, 0x04, 1, 2, 3]);
      const server = fakeServer({
        'DELETE /sessions/u': () => json({ ok: true }),
        'GET /sessions/u/traces': () =>
          json({
            traces: [
              { filename: 'trace-1.zip', sizeBytes: zip.byteLength, createdAt: 1, modifiedAt: 1 },
              { filename: '../escape.zip', sizeBytes: 1, createdAt: 1, modifiedAt: 1 },
            ],
          }),
        'GET /sessions/u/traces/trace-1.zip': () => new Response(zip, { status: 200 }),
      });
      const client = new CamofoxClient({ userId: 'u', apiKey: 'api', fetch: server.fetch });

      const first = await saveTraces(client, dir);
      assert.deepEqual(server.calls.map((c) => `${c.method} ${c.path}`), [
        'DELETE /sessions/u',
        'GET /sessions/u/traces',
        'GET /sessions/u/traces/trace-1.zip',
      ]);
      assert.equal(server.calls[2].auth, 'Bearer api');
      assert.deepEqual(first, [{ filename: 'trace-1.zip', path: path.join(dir, 'trace-1.zip'), sizeBytes: 7, downloaded: true }]);
      assert.deepEqual(new Uint8Array(await readFile(path.join(dir, 'trace-1.zip'))), zip);

      const second = await saveTraces(client, dir, { closeSession: false });
      assert.equal(second[0].downloaded, false);
      assert.equal(server.calls.filter((c) => c.path.endsWith('trace-1.zip')).length, 1);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});
