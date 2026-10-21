/**
 * Session set-up around a CamofoxClient: cookies from a Netscape cookie file,
 * an optional traced first tab, and saving the trace zips afterwards.
 *
 * Proxy and GeoIP are not here on purpose. camofox-browser reads PROXY_* from
 * its own environment when it starts, and turns on GeoIP (timezone, locale,
 * coordinates matched to the proxy's exit IP) by itself whenever a proxy is
 * configured. No REST call changes either, so a client cannot set them; see
 * deploy/camofox.env.example.
 */
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import type { CamofoxClient } from './client.js';
import type { CamofoxCookie, CreateTabResponse, ImportCookiesResponse } from './types.js';

export interface SkippedCookieLine {
  line: number;
  reason: string;
}

export interface ParsedCookieFile {
  cookies: CamofoxCookie[];
  /** Lines that looked like cookies but were not used, and why. Comments and blank lines are not listed. */
  skipped: SkippedCookieLine[];
}

/**
 * Parse a Netscape cookie file (curl, yt-dlp and the "cookies.txt" browser
 * extensions write this format): seven tab-separated fields per line,
 * `domain  includeSubdomains  path  secure  expiry  name  value`, with a
 * `#HttpOnly_` prefix on HttpOnly cookies.
 *
 * Expiry 0 (or anything that is not a positive number) means a session
 * cookie, which Playwright spells -1; sending 0 would set an already-expired
 * cookie that the browser drops without a word. Cookies whose expiry has
 * passed are skipped and reported rather than sent.
 */
export function parseNetscapeCookies(text: string, now: Date = new Date()): ParsedCookieFile {
  const cookies: CamofoxCookie[] = [];
  const skipped: SkippedCookieLine[] = [];
  const nowSeconds = Math.floor(now.getTime() / 1000);

  for (const [index, rawLine] of text.replace(/^﻿/, '').split(/\r?\n/).entries()) {
    const line = rawLine.trim();
    if (!line) continue;
    const httpOnly = line.startsWith('#HttpOnly_');
    if (line.startsWith('#') && !httpOnly) continue;

    const fields = (httpOnly ? line.slice('#HttpOnly_'.length) : line).split('\t');
    if (fields.length < 7) {
      skipped.push({ line: index + 1, reason: `expected 7 tab-separated fields, found ${fields.length}` });
      continue;
    }
    const [domain, , cookiePath, secure, expiry, name] = fields;
    const value = fields.slice(6).join('\t');
    if (!domain || !name) {
      skipped.push({ line: index + 1, reason: 'missing domain or name' });
      continue;
    }
    const seconds = Number(expiry);
    const expires = Number.isFinite(seconds) && seconds > 0 ? seconds : -1;
    if (expires !== -1 && expires <= nowSeconds) {
      skipped.push({ line: index + 1, reason: `${name} for ${domain} expired ${new Date(expires * 1000).toISOString()}` });
      continue;
    }
    cookies.push({
      name,
      value,
      domain,
      path: cookiePath || '/',
      expires,
      httpOnly,
      secure: secure.toUpperCase() === 'TRUE',
    });
  }
  return { cookies, skipped };
}

/** Read and parse a Netscape cookie file. A leading `~` is the home directory. */
export async function readNetscapeCookieFile(file: string, now?: Date): Promise<ParsedCookieFile> {
  return parseNetscapeCookies(await readFile(expandHome(file), 'utf8'), now);
}

export interface InitSessionOptions {
  /** Netscape cookie files to import before any tab opens. */
  cookieFiles?: string[];
  /** Open a first tab. Required for tracing: the server only accepts trace on a session's first tab. */
  firstTab?: { sessionKey: string; url?: string; trace?: boolean };
  userId?: string;
}

export interface InitSessionResult {
  userId: string;
  cookies: (ImportCookiesResponse & { file: string; skipped: SkippedCookieLine[] }) [];
  tab: CreateTabResponse | null;
}

/**
 * Prepare a session: check the server is up, import cookie files into the
 * user's context, and optionally open the first tab (traced or not).
 */
export async function initSession(client: CamofoxClient, options: InitSessionOptions = {}): Promise<InitSessionResult> {
  const userId = options.userId ?? client.userId;
  const health = await client.health();
  if (!health.ok) throw new Error(`camofox-browser at ${client.baseUrl} reports it is not healthy`);

  const cookies: InitSessionResult['cookies'] = [];
  for (const file of options.cookieFiles ?? []) {
    const parsed = await readNetscapeCookieFile(file);
    if (!parsed.cookies.length) throw new Error(`${file}: no usable cookies (${parsed.skipped.length} lines skipped)`);
    const imported = await client.importCookies(parsed.cookies, { userId });
    cookies.push({ ...imported, file, skipped: parsed.skipped });
  }

  const tab = options.firstTab
    ? await client.createTab({ ...options.firstTab, userId })
    : null;
  return { userId, cookies, tab };
}

export interface SavedTrace {
  filename: string;
  path: string;
  sizeBytes: number;
  /** False when a file of the same name and size was already in the directory. */
  downloaded: boolean;
}

/**
 * Close the session so the server writes its trace, then download every trace
 * zip of the user into `outDir`. Closing the session closes its tabs: call
 * this when the run is over. Open a zip at https://trace.playwright.dev or
 * with `npx playwright show-trace <file>`.
 */
export async function saveTraces(
  client: CamofoxClient,
  outDir: string,
  options: { userId?: string; closeSession?: boolean } = {},
): Promise<SavedTrace[]> {
  const userId = options.userId ?? client.userId;
  if (options.closeSession ?? true) await client.closeSession({ userId });

  const dir = expandHome(outDir);
  await mkdir(dir, { recursive: true });
  const saved: SavedTrace[] = [];
  for (const trace of await client.listTraces({ userId })) {
    // The name comes from the server; never let it pick a directory.
    const filename = path.basename(trace.filename);
    if (!filename.endsWith('.zip') || filename !== trace.filename) continue;
    const target = path.join(dir, filename);
    const existing = await stat(target).catch(() => null);
    if (existing?.size === trace.sizeBytes) {
      saved.push({ filename, path: target, sizeBytes: trace.sizeBytes, downloaded: false });
      continue;
    }
    const bytes = await client.downloadTrace(filename, { userId });
    await writeFile(target, bytes);
    saved.push({ filename, path: target, sizeBytes: bytes.byteLength, downloaded: true });
  }
  return saved;
}

function expandHome(file: string): string {
  return file === '~' || file.startsWith('~/') ? path.join(os.homedir(), file.slice(1)) : file;
}
