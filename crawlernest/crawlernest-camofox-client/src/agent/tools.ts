import type Anthropic from '@anthropic-ai/sdk';

import type { NavigateMacro } from '../types.js';

/** Every action the agent can take, after its input has been validated. */
export type BrowserAction =
  | { kind: 'navigate'; url: string }
  | { kind: 'navigate'; macro: NavigateMacro; query: string }
  | { kind: 'click'; ref: string }
  | { kind: 'type_text'; ref: string; text: string; pressEnter: boolean; clear: boolean }
  | { kind: 'read_more' }
  | { kind: 'finish'; status: 'completed' | 'failed'; summary: string };

export const NAVIGATE_MACROS: readonly NavigateMacro[] = [
  '@google_search',
  '@youtube_search',
  '@amazon_search',
  '@reddit_search',
  '@reddit_subreddit',
  '@wikipedia_search',
  '@twitter_search',
  '@yelp_search',
  '@spotify_search',
  '@netflix_search',
  '@linkedin_search',
  '@instagram_search',
  '@tiktok_search',
  '@twitch_search',
];

/**
 * Tool definitions. The array is built once and never changes during a run:
 * the tool set is part of the cache prefix and of what thinking blocks are
 * bound to. `eager_input_streaming` is set because the loop streams; that
 * turns off server-side validation, so parseAction validates every input.
 */
export const BROWSER_TOOLS: Anthropic.Beta.BetaTool[] = [
  {
    name: 'navigate',
    description:
      'Load a page in the current tab. Give either `url`, or `macro` and `query` to open a site search ' +
      '(for example macro "@amazon_search", query "python programming"). Returns the new page snapshot.',
    eager_input_streaming: true,
    input_schema: {
      type: 'object',
      properties: {
        url: { type: 'string', description: 'Absolute http(s) URL.' },
        macro: { type: 'string', enum: [...NAVIGATE_MACROS], description: 'Search macro; requires query.' },
        query: { type: 'string', description: 'Search terms for the macro.' },
      },
      additionalProperties: false,
    },
  },
  {
    name: 'click',
    description: 'Click the element with this ref from the most recent snapshot. Returns the new page snapshot.',
    eager_input_streaming: true,
    input_schema: {
      type: 'object',
      properties: { ref: { type: 'string', description: 'Element ref such as "e12", exactly as in the latest snapshot.' } },
      required: ['ref'],
      additionalProperties: false,
    },
  },
  {
    name: 'type_text',
    description:
      'Type text into the input element with this ref from the most recent snapshot. The field is cleared first ' +
      'unless clear is false. Set press_enter to submit (e.g. run a search). Returns the new page snapshot.',
    eager_input_streaming: true,
    input_schema: {
      type: 'object',
      properties: {
        ref: { type: 'string', description: 'Element ref such as "e3", exactly as in the latest snapshot.' },
        text: { type: 'string' },
        press_enter: { type: 'boolean', description: 'Press Enter after typing. Default false.' },
        clear: { type: 'boolean', description: 'Clear the field before typing. Default true.' },
      },
      required: ['ref', 'text'],
      additionalProperties: false,
    },
  },
  {
    name: 'read_more',
    description:
      'Read the next part of a long page whose snapshot was truncated. Refs from that part become usable; ' +
      'refs from the earlier part stay valid.',
    eager_input_streaming: true,
    input_schema: { type: 'object', properties: {}, additionalProperties: false },
  },
  {
    name: 'finish',
    description: 'End the task. Call once, when the task is done or certainly cannot be done.',
    eager_input_streaming: true,
    input_schema: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['completed', 'failed'] },
        summary: { type: 'string', description: 'What was done and what the page shows, with requested values.' },
      },
      required: ['status', 'summary'],
      additionalProperties: false,
    },
  },
];

const REF = /^e\d+$/;

/**
 * Validate a tool_use input. Returns the action, or an error message to send
 * back as an is_error tool_result. Ref membership in the current snapshot is
 * checked separately, by the loop, because it depends on run state.
 */
export function parseAction(name: string, input: unknown): BrowserAction | { error: string } {
  if (typeof input !== 'object' || input === null || Array.isArray(input)) {
    return { error: `INVALID_JSON: ${JSON.stringify(input)}` };
  }
  const args = input as Record<string, unknown>;
  const str = (key: string) => (typeof args[key] === 'string' ? (args[key] as string) : undefined);
  const bool = (key: string, fallback: boolean): boolean | null =>
    args[key] === undefined ? fallback : typeof args[key] === 'boolean' ? (args[key] as boolean) : null;

  switch (name) {
    case 'navigate': {
      const url = str('url');
      const macro = str('macro');
      const query = str('query');
      if (url && !macro) {
        if (!/^https?:\/\//i.test(url)) return { error: `url must be an absolute http(s) URL, got ${JSON.stringify(url)}` };
        return { kind: 'navigate', url };
      }
      if (macro && !url) {
        if (!NAVIGATE_MACROS.includes(macro as NavigateMacro)) return { error: `unknown macro ${JSON.stringify(macro)}` };
        if (!query) return { error: 'macro needs a non-empty query' };
        return { kind: 'navigate', macro: macro as NavigateMacro, query };
      }
      return { error: 'give either url, or macro with query' };
    }
    case 'click': {
      const ref = str('ref');
      if (!ref || !REF.test(ref)) return { error: `ref must look like "e12", got ${JSON.stringify(args.ref)}` };
      return { kind: 'click', ref };
    }
    case 'type_text': {
      const ref = str('ref');
      const text = str('text');
      const pressEnter = bool('press_enter', false);
      const clear = bool('clear', true);
      if (!ref || !REF.test(ref)) return { error: `ref must look like "e12", got ${JSON.stringify(args.ref)}` };
      if (text === undefined) return { error: 'text is required' };
      if (pressEnter === null || clear === null) return { error: 'press_enter and clear must be booleans' };
      return { kind: 'type_text', ref, text, pressEnter, clear };
    }
    case 'read_more':
      return { kind: 'read_more' };
    case 'finish': {
      const status = str('status');
      const summary = str('summary');
      if (status !== 'completed' && status !== 'failed') return { error: 'status must be "completed" or "failed"' };
      if (!summary) return { error: 'summary is required' };
      return { kind: 'finish', status, summary };
    }
    default:
      return { error: `unknown tool ${JSON.stringify(name)}` };
  }
}
