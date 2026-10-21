#!/usr/bin/env node
/**
 * camofox-session init [--cookies FILE]... [--url URL] [--session-key KEY] [--trace]
 * camofox-session save-traces [--out DIR]
 *
 * Reads CAMOFOX_URL, CAMOFOX_USER_ID, CAMOFOX_ACCESS_KEY and CAMOFOX_API_KEY
 * from the environment; load deploy/camofox.env with `node --env-file`.
 * Traces go to <repo>/.local/logs/camofox-traces/ unless --out says otherwise.
 */
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

import { CamofoxClient, DEFAULT_BASE_URL } from '../client.js';
import { CamofoxError } from '../errors.js';
import { initSession, saveTraces } from '../session.js';

const USAGE = `usage:
  camofox-session init [--cookies FILE]... [--url URL] [--session-key KEY] [--trace]
  camofox-session save-traces [--out DIR] [--keep-session]`;

async function main(argv: string[]): Promise<number> {
  const [command, ...rest] = argv;
  const { values } = parseArgs({
    args: rest,
    options: {
      cookies: { type: 'string', multiple: true },
      url: { type: 'string' },
      'session-key': { type: 'string', default: 'crawlernest' },
      trace: { type: 'boolean', default: false },
      out: { type: 'string' },
      'keep-session': { type: 'boolean', default: false },
    },
  });

  const client = new CamofoxClient({
    baseUrl: process.env.CAMOFOX_URL || DEFAULT_BASE_URL,
    userId: process.env.CAMOFOX_USER_ID || 'crawlernest',
    accessKey: process.env.CAMOFOX_ACCESS_KEY || undefined,
    apiKey: process.env.CAMOFOX_API_KEY || undefined,
  });

  if (command === 'init') {
    const wantsTab = Boolean(values.url || values.trace);
    const result = await initSession(client, {
      cookieFiles: values.cookies ?? [],
      firstTab: wantsTab ? { sessionKey: values['session-key']!, url: values.url, trace: values.trace } : undefined,
    });
    for (const imported of result.cookies) {
      console.log(`cookies: ${imported.count} from ${imported.file} into ${result.userId} (${imported.batches} request(s))`);
      for (const skip of imported.skipped) console.log(`  skipped line ${skip.line}: ${skip.reason}`);
    }
    if (result.tab) {
      const navigation = result.tab.navigationOk === false ? ` (HTTP ${result.tab.httpStatus})` : '';
      console.log(`tab: ${result.tab.tabId} ${result.tab.url}${navigation}${values.trace ? ', tracing' : ''}`);
    }
    if (!result.cookies.length && !result.tab) console.log(`camofox-browser at ${client.baseUrl} is up; nothing to do`);
    return 0;
  }

  if (command === 'save-traces') {
    const outDir = values.out ?? path.join(repoRoot(), '.local', 'logs', 'camofox-traces');
    const saved = await saveTraces(client, outDir, { closeSession: !values['keep-session'] });
    if (!saved.length) console.log(`no traces for ${client.userId}; was the first tab opened with --trace?`);
    for (const trace of saved) {
      console.log(`${trace.downloaded ? 'saved' : 'already there'}: ${trace.path} (${trace.sizeBytes} bytes)`);
    }
    return 0;
  }

  console.error(USAGE);
  return 2;
}

/** The checkout root: the nearest ancestor holding both crawlernest/ and deploy/. */
function repoRoot(): string {
  let dir = path.dirname(fileURLToPath(import.meta.url));
  for (;;) {
    if (existsSync(path.join(dir, 'crawlernest')) && existsSync(path.join(dir, 'deploy'))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) return process.cwd();
    dir = parent;
  }
}

main(process.argv.slice(2)).then(
  (code) => process.exit(code),
  (error) => {
    if (error instanceof CamofoxError && error.kind === 'network') {
      console.error(`${error.message}: is camofox-browser running at ${process.env.CAMOFOX_URL || DEFAULT_BASE_URL}?`);
    } else {
      console.error(error instanceof Error ? error.message : error);
    }
    process.exit(1);
  },
);
