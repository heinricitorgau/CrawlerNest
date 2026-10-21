# crawlernest-camofox-client

Typed client for the [camofox-browser](../../camofox-browser/) REST API (`http://localhost:9377`) and a parser that turns
its accessibility snapshots into the CrawlerNest `CrawlPage` format. It has no runtime dependencies and needs Node 20 or later.

```ts
import { CamofoxClient, CamofoxError, parseSnapshot } from '@crawlernest/camofox-client';

const camofox = new CamofoxClient({ userId: 'qs-crawler', apiKey: process.env.CAMOFOX_ACCESS_KEY });

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

Every method accepts a `userId` override; otherwise the client's `userId` is sent.

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

## Tests

```bash
npm install && npm test
```

The tests replace `fetch`, so the server does not have to be running. They have not been run against a live server.
CI runs them in `.github/workflows/camofox-client-tests.yml` whenever this folder changes.
