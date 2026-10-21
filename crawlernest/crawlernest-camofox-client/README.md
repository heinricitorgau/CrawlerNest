# crawlernest-camofox-client

Typed client for the [camofox-browser](../../camofox-browser/) REST API (`http://localhost:9377`), a parser that turns
its accessibility snapshots into the CrawlerNest `CrawlPage` format, and a [Claude agent loop](#the-browsing-agent) that
browses with both. Needs Node 20 or later. The client and parser have no runtime dependencies; only the agent, a separate
entry point (`@crawlernest/camofox-client/agent`), loads `@anthropic-ai/sdk`.

```ts
import { CamofoxClient, CamofoxError, parseSnapshot } from '@crawlernest/camofox-client';

const camofox = new CamofoxClient({ userId: 'qs-crawler', accessKey: process.env.CAMOFOX_ACCESS_KEY });

const page = await camofox.withTab({ sessionKey: 'qs-2026', url: 'https://www.topuniversities.com/' }, async (tabId) => {
  const first = parseSnapshot(await camofox.snapshot(tabId));
  const search = first.interactive.find((e) => e.role === 'searchbox');
  if (search) await camofox.type(tabId, search.ref, 'National Taiwan University', { clear: true, submit: true });
  return parseSnapshot(await camofox.snapshot(tabId, { includeScreenshot: true }));
});
```

| Method | Endpoint |
| --- | --- |
| `createTab({ sessionKey, url?, trace? })` | `POST /tabs` |
| `snapshot(tabId, { includeScreenshot?, offset? })` | `GET /tabs/:id/snapshot` |
| `click(tabId, 'e1' \| { ref } \| { selector })` | `POST /tabs/:id/click` |
| `type(tabId, target, text, { clear?, submit? })` | `POST /tabs/:id/type` |
| `navigate(tabId, url \| { macro: '@google_search', query })` | `POST /tabs/:id/navigate` |
| `closeTab(tabId)` | `DELETE /tabs/:id` (a tab the server no longer knows counts as closed) |
| `withTab(request, work)` | creates a tab and closes it when `work` ends, even if it throws |
| `health()` | `GET /health` |
| `importCookies(cookies)` | `POST /sessions/:userId/cookies`, in batches of at most 500 |
| `closeSession()` | `DELETE /sessions/:userId` (this is when a traced session writes its zip) |
| `listTraces()`, `downloadTrace(filename)` | `GET /sessions/:userId/traces[/:filename]` |

Every method accepts a `userId` override; otherwise the client's `userId` is sent.

The server has two keys. `accessKey` (its `CAMOFOX_ACCESS_KEY`) is sent on every route. `apiKey` (its
`CAMOFOX_API_KEY`) replaces it on the cookie and trace routes, because cookie import accepts no other key.

## Retries

A failed call is retried at most twice (`retry.maxRetries`), with exponential backoff and jitter. Whether to retry
depends on whether sending the call again is safe:

| Failure | Snapshot, navigate, close | Click, type, create tab |
| --- | --- | --- |
| Connection refused | retried | retried (the call never arrived) |
| Timeout, other network error, 502, 504 | retried | **not retried**: the click may already have happened |
| 503 (`session_expired`, server busy) | retried | retried |
| `recovery: "create_new_tab"` (crashed or unresponsive tab), 404, 410 | not retried | not retried |
| 409 `page_changed`, other 4xx | not retried | not retried |

`type` with `clear: true` and no `submit` counts as safe to repeat, because the field ends up with the same value.

A failure that is not retried throws a `CamofoxError`. It carries `kind` (`http`, `network`, `timeout` or `protocol`),
`status`, the server's `code` and `recovery`, and `attempts`. Two helpers say what to do next:

- `needsNewTab`: the tab is gone. Open a new one.
- `needsFreshSnapshot`: the refs are stale. Take a snapshot and look the element up again.

## The page format

`parseSnapshot(response)` returns a `CrawlPage` (see [`src/types.ts`](src/types.ts)):

- `tree`: every snapshot line as a `PageNode` with `role`, `name`, `ref`, `attributes`, inline `text` and `/key:` props
- `headings`, `links` (with `href` from `/url`), `textBlocks`
- `interactive`: every element that has a ref, which are the elements `click` and `type` accept
- `tables`: the server's DOM summary of `<table>` elements when it sends one (`origin: "dom"`), otherwise the tables
  rebuilt from the aria tree (`origin: "aria"`)
- `forms`: the server's DOM summary of forms
- `completeness`: whether the snapshot was truncated, and the `nextOffset` for the next window
- `warnings`: lines the parser could not read. It never throws.

The snapshot has no `<title>`. `primaryHeading` is the first level-1 heading, and it is not the document title.

A page longer than 80,000 characters arrives in windows. Each window is the next part of the snapshot plus the last
5,000 characters, so the pagination links are always present. Pass `completeness.nextOffset` to
`snapshot(tabId, { offset })` to read the next window. A window that starts mid-line puts that line in `warnings`.

## Sessions: cookies, proxy, traces

```bash
cp deploy/camofox.env.example deploy/camofox.env       # gitignored; fill in keys and proxy
cd camofox-browser && node --env-file=../deploy/camofox.env server.js

cd crawlernest/crawlernest-camofox-client && npm run build
node --env-file=../../deploy/camofox.env dist/src/bin/camofox-session.js \
  init --cookies ~/.camofox/cookies/target.txt --url https://example.com/ --trace
# ... run the crawl or the agent with the same CAMOFOX_USER_ID ...
node --env-file=../../deploy/camofox.env dist/src/bin/camofox-session.js save-traces
```

- **Cookies:** `init --cookies` reads a Netscape cookie file (the `cookies.txt` that curl, yt-dlp and the browser
  extensions write) and imports it into the user's browser context before any tab opens. It reports expired or
  malformed lines and does not send them. A session cookie (expiry 0) goes as `-1`; sent as `0`, Playwright would set
  it already expired. In code, use `readNetscapeCookieFile` and `client.importCookies`, or `initSession`.
- **Proxy and GeoIP need no client code.** camofox-browser reads `PROXY_*` from its environment when it starts, and no
  REST call changes them. With a proxy it turns on GeoIP itself, so each context takes the timezone, locale and
  coordinates of the exit IP. All of it is in [`deploy/camofox.env.example`](../../deploy/camofox.env.example).
  `PROXY_STRATEGY=backconnect` reads `PROXY_BACKCONNECT_HOST`/`PORT`, not `PROXY_HOST`/`PORT`. If it is missing a
  value, the server starts without a proxy rather than failing, so check its log for `proxy pool created`.
- **Traces:** the server accepts `trace` only on a session's first tab (`init --trace`, or
  `createTab({ trace: true })`), and writes the zip only when the session closes. `save-traces` closes the session,
  then downloads every zip to `.local/logs/camofox-traces/`; `saveTraces(client, dir)` does the same in code. Open a
  zip at https://trace.playwright.dev or with `npx playwright show-trace`.

## The browsing agent

`BrowserAgent` gives Claude a task and a Camofox tab, and loops until Claude calls `finish`:

```ts
import { CamofoxClient } from '@crawlernest/camofox-client';
import { BrowserAgent } from '@crawlernest/camofox-client/agent';

const agent = new BrowserAgent({
  browser: new CamofoxClient({ userId: 'agent' }),
  // Optional guard: refuse anything off amazon.com.
  beforeAction: (action) => !('url' in action) || action.url.startsWith('https://www.amazon.com/'),
  onStep: (step) => console.log(step.step, step.tool, step.ok ? 'ok' : step.error),
});

const result = await agent.run({
  task: 'Search Amazon for Python programming books and open the first result',
  startUrl: 'https://www.amazon.com/',
});
// result.status: completed | failed | max_steps | refused | stopped
console.log(result.status, result.summary, result.finalUrl);
```

Credentials come from `ANTHROPIC_API_KEY` (or an `ant auth login` profile). The model is `claude-opus-5-5` at effort
`high`; both are options.

Each step works like this:

1. The current snapshot goes to Claude inside `<page_snapshot>` tags. The system prompt ([`src/agent/prompt.ts`](src/agent/prompt.ts))
   says that tag holds untrusted page content, and the snapshot is escaped so a page cannot close the tag itself.
2. Claude answers with one tool call: `navigate` (a URL or a search macro), `click`, `type_text`, `read_more` (the next
   window of a truncated page) or `finish`. Parallel calls are off, because every action invalidates the refs a second
   call would use. Instead of free-form JSON, each action is a tool with a schema, and the loop validates every input
   (`parseAction`).
3. **The loop checks the ref before Camofox sees it.** It keeps the refs of the latest snapshot. A ref that is not
   among them, whether invented or left over from the previous page, is refused with an error result, and the browser
   is not called.
4. After the action, a fresh snapshot is the tool result, so Claude always decides from the page as it is now.
   - A `page_changed` error from Camofox returns the current page and lets Claude choose again.
   - A lost tab ends the run with status `failed`.

**What the loop guarantees:**

- **The history is append-only.** Thinking blocks are bound to it, and the prompt cache reuses it.
- **Old snapshots are not deleted on the client.** Once the input passes 50k tokens, server-side context editing
  (`clear_tool_uses_20250919`) clears all but the last three tool results.
- **A refusal is retried on a fallback model** (`fallbacks: "default"`), and is reported as `refused` if that refuses too.
- **A tool call cut off at `max_tokens` is never run.**

The system prompt forbids signing in, buying, and submitting personal details. That is an instruction, not a control;
`beforeAction` is the control. Use it for an allow-list or a human confirmation.

## Tests

```bash
npm install && npm test
```

The client tests replace `fetch`, and the agent tests replace both the browser and the model, so neither server nor
API key is needed. None of it has run against a live camofox-browser or the Claude API yet.
CI runs them in `.github/workflows/camofox-client-tests.yml` whenever this folder changes.
