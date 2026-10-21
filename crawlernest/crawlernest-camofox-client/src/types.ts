/**
 * Wire types for the camofox-browser REST API (see camofox-browser/openapi.json)
 * and the CrawlerNest page format the snapshot parser produces.
 */

// ---------------------------------------------------------------------------
// Client configuration
// ---------------------------------------------------------------------------

export interface RetryPolicy {
  /** Retries after the first attempt. The total is maxRetries + 1 attempts. */
  maxRetries: number;
  /** Delay before the first retry; doubled for each later retry. */
  baseDelayMs: number;
  /** Upper bound for a single delay. */
  maxDelayMs: number;
}

export interface CamofoxClientOptions {
  /** Default http://localhost:9377. */
  baseUrl?: string;
  /** Session owner sent on every call. Camofox isolates browser contexts per userId. */
  userId: string;
  /** Sent as `Authorization: Bearer <apiKey>` when CAMOFOX_ACCESS_KEY / CAMOFOX_API_KEY is set on the server. */
  apiKey?: string;
  /** Timeout for one attempt. Default 60 000 ms (the server's own handler timeout is 30 s plus queueing). */
  timeoutMs?: number;
  retry?: Partial<RetryPolicy>;
  /** Injected for tests; defaults to the global fetch (Node >= 18). */
  fetch?: typeof fetch;
  /** Injected for tests; defaults to setTimeout. */
  sleep?: (ms: number) => Promise<void>;
  /** Called before every retry. */
  onRetry?: (info: RetryInfo) => void;
}

export interface RetryInfo {
  method: string;
  path: string;
  attempt: number;
  delayMs: number;
  error: Error;
}

// ---------------------------------------------------------------------------
// Requests
// ---------------------------------------------------------------------------

export interface CreateTabRequest {
  /** Tab group; tabs that share it can be closed together. */
  sessionKey: string;
  url?: string;
  /** Overrides the client's userId for this call. */
  userId?: string;
  /** Playwright tracing. Must be set on the first tab of a session. */
  trace?: boolean;
}

export interface SnapshotOptions {
  includeScreenshot?: boolean;
  /** Character offset into a truncated snapshot (use the previous response's nextOffset). */
  offset?: number;
  userId?: string;
}

/** Macros camofox-browser 1.18 expands server-side (lib/macros.js). */
export type NavigateMacro =
  | '@google_search'
  | '@youtube_search'
  | '@amazon_search'
  | '@reddit_search'
  | '@reddit_subreddit'
  | '@wikipedia_search'
  | '@twitter_search'
  | '@yelp_search'
  | '@spotify_search'
  | '@netflix_search'
  | '@linkedin_search'
  | '@instagram_search'
  | '@tiktok_search'
  | '@twitch_search';

export type NavigateTarget =
  | { url: string }
  | { macro: NavigateMacro; query: string };

/** An element is addressed by a snapshot ref ("e1") or, as a fallback, a CSS selector. */
export type ElementTarget = { ref: string } | { selector: string };

export interface ClickOptions {
  doubleClick?: boolean;
  userId?: string;
}

export interface TypeOptions {
  /** Clear the field before typing. */
  clear?: boolean;
  /** Press Enter after typing. */
  submit?: boolean;
  userId?: string;
}

// ---------------------------------------------------------------------------
// Responses
// ---------------------------------------------------------------------------

export interface CreateTabResponse {
  tabId: string;
  url: string;
  /** HTTP status of the initial navigation, when a url was given. */
  httpStatus?: number | null;
  /** False when the initial document returned HTTP >= 400. */
  navigationOk?: boolean;
}

export interface Screenshot {
  /** Base64-encoded image. */
  data: string;
  mimeType: string;
}

export interface StructureFormField {
  label?: string;
  id?: string;
  name?: string;
  type?: string;
  ref?: string;
  value?: string;
  options?: { label: string; value: string; selected: boolean }[];
  optionsTruncated?: boolean;
  [key: string]: unknown;
}

export interface StructureForm {
  label?: string;
  id?: string;
  name?: string;
  method: string;
  fields: StructureFormField[];
  fieldsTruncated: boolean;
  submitControls: { label?: string; id?: string; name?: string; disabled: boolean; ref?: string }[];
}

export interface StructureTable {
  label?: string;
  id?: string;
  headers: string[];
  columns: string[];
  /** Rows in the DOM, not rows returned. */
  rowCount: number;
  rows: string[][];
  rowsTruncated: boolean;
}

/** Bounded DOM summary of forms and tables (lib/page-structure.js). Null when extraction failed. */
export interface PageStructure {
  forms: StructureForm[];
  formsTruncated: boolean;
  tables: StructureTable[];
  tablesTruncated: boolean;
  evidenceLimits?: unknown[];
}

export interface SnapshotResponse {
  url: string;
  /** Playwright aria-snapshot YAML with `[eN]` refs on interactive elements. */
  snapshot: string;
  /** Absent on the Google results fast path. */
  structure?: PageStructure | null;
  refsCount: number;
  truncated: boolean;
  totalChars: number;
  hasMore?: boolean;
  nextOffset?: number | null;
  screenshot?: Screenshot;
}

export interface NavigateResponse {
  ok: boolean;
  tabId: string;
  url: string;
  httpStatus?: number | null;
  navigationOk?: boolean;
}

export interface ActionResponse {
  ok: boolean;
  url?: string;
  /** False when the page navigated and the old refs are gone: take a new snapshot. */
  refsAvailable?: boolean;
  [key: string]: unknown;
}

export interface CloseTabResponse {
  ok: boolean;
  /** True when the server no longer knew the tab (already closed, or reaped). */
  alreadyClosed?: boolean;
}

/** What the server tells the caller to do after an error (handleRouteError in server.js). */
export type CamofoxRecovery = 'retry' | 'create_new_tab' | 'snapshot_then_retry';

export interface CamofoxErrorBody {
  error: string;
  code?: string;
  retryable?: boolean;
  recovery?: CamofoxRecovery | string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// CrawlerNest page format
// ---------------------------------------------------------------------------

/** One line of the aria snapshot, with its children. */
export interface PageNode {
  /** ARIA role ("link", "heading", "row"), or "text" for a bare text line. */
  role: string;
  /** Accessible name: the quoted string after the role. */
  name: string | null;
  /** Camofox element ref for click/type; only interactive roles carry one. */
  ref: string | null;
  /** Bracketed attributes: `[level=2]` -> { level: "2" }, `[checked]` -> { checked: true }. */
  attributes: Record<string, string | true>;
  /** Text after the colon: `- paragraph: Hello` -> "Hello". */
  text: string | null;
  /** Child `/key: value` lines, e.g. { url: "https://..." } for a link. */
  props: Record<string, string>;
  children: PageNode[];
}

export interface PageHeading {
  level: number | null;
  text: string;
}

export interface PageLink {
  text: string;
  href: string | null;
  ref: string | null;
}

export interface InteractiveElement {
  ref: string;
  role: string;
  name: string | null;
  /** Current value for textboxes and comboboxes, when the snapshot shows one. */
  value: string | null;
  /** Flag and keyed attributes (checked, disabled, expanded, ...). */
  states: Record<string, string | true>;
}

export interface PageTable {
  /** "dom" tables come from the server's structure summary; "aria" ones from the snapshot tree. */
  origin: 'dom' | 'aria';
  label: string | null;
  headers: string[];
  rows: string[][];
  /** True when the source says rows were cut, or the snapshot itself was truncated. */
  rowsTruncated: boolean;
}

export interface PageCompleteness {
  /** The snapshot text is one window of a longer snapshot. */
  truncated: boolean;
  totalChars: number;
  hasMore: boolean;
  /** Pass to snapshot({ offset }) for the next window. */
  nextOffset: number | null;
}

/** The CrawlerNest-internal representation of a page captured through Camofox. */
export interface CrawlPage {
  source: 'camofox';
  url: string;
  capturedAt: string;
  /**
   * First level-1 heading, else the first heading. The aria snapshot carries no
   * <title>, so this is not the document title.
   */
  primaryHeading: string | null;
  headings: PageHeading[];
  links: PageLink[];
  interactive: InteractiveElement[];
  /** Paragraph, text and list-item content in document order. */
  textBlocks: string[];
  tables: PageTable[];
  forms: StructureForm[];
  completeness: PageCompleteness;
  screenshot: Screenshot | null;
  tree: PageNode[];
  /** Lines the parser could not read; empty on a well-formed snapshot. */
  warnings: string[];
}
