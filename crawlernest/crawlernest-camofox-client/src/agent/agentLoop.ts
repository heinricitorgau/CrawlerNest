/**
 * A Claude tool-use loop that drives a Camofox tab.
 *
 *   snapshot -> Claude picks one action (a tool call) -> the loop checks the
 *   ref against the latest snapshot -> Camofox runs it -> new snapshot goes
 *   back as the tool result -> ... -> Claude calls finish
 *
 * Claude never sees a ref it could invent safely: the loop keeps the set of
 * refs from the current snapshot and refuses any other without calling
 * Camofox. The conversation is append-only (thinking blocks are bound to it);
 * old snapshots are cleared server-side by context editing, not by rewriting
 * history.
 */
import Anthropic from '@anthropic-ai/sdk';

import type { CamofoxClient } from '../client.js';
import { CamofoxError } from '../errors.js';
import { parseSnapshot } from '../snapshotParser.js';
import type { CrawlPage, SnapshotResponse } from '../types.js';
import { BROWSER_AGENT_SYSTEM_PROMPT, initialUserMessage } from './prompt.js';
import { BROWSER_TOOLS, parseAction } from './tools.js';
import type { BrowserAction } from './tools.js';

export const DEFAULT_AGENT_MODEL = 'claude-opus-5-5';

/** The parts of CamofoxClient the loop uses; a fake can stand in for tests. */
export type BrowserPort = Pick<CamofoxClient, 'createTab' | 'snapshot' | 'click' | 'type' | 'navigate' | 'closeTab'>;

export type MessageParams = Anthropic.Beta.Messages.MessageCreateParamsNonStreaming;
export type CreateMessage = (params: MessageParams) => Promise<Anthropic.Beta.BetaMessage>;

export type Effort = 'low' | 'medium' | 'high' | 'xhigh' | 'max';

export interface BrowserAgentOptions {
  browser: BrowserPort;
  /** Used to build the default createMessage. Defaults to `new Anthropic()` (ANTHROPIC_API_KEY or an `ant auth` profile). */
  anthropic?: Anthropic;
  /** Replaces the API call; for tests or a custom transport. */
  createMessage?: CreateMessage;
  model?: string;
  /** Default "high": multi-step tool use benefits from it, and Opus 5.5 would otherwise default to "medium". */
  effort?: Effort;
  /** Model calls before the run is stopped. Default 25. */
  maxSteps?: number;
  /** Per-response output cap. Default 64 000 (the loop streams, so a large cap does not risk HTTP timeouts). */
  maxTokens?: number;
  /**
   * Called before every click, type or navigation. Return false to refuse it;
   * Claude is told the operator declined. Use it for allow-lists or a human
   * confirmation step.
   */
  beforeAction?: (action: Exclude<BrowserAction, { kind: 'read_more' | 'finish' }>, page: CrawlPage) => boolean | Promise<boolean>;
  /** Called after every executed tool call. */
  onStep?: (step: AgentStep) => void;
}

export interface BrowserTask {
  /** What to do, in the user's words. */
  task: string;
  /** Page to open first. Ignored when tabId is given. */
  startUrl?: string;
  /** Reuse an open tab instead of creating (and later closing) one. */
  tabId?: string;
  /** Tab group for a created tab. Default "browser-agent". */
  sessionKey?: string;
}

export interface AgentStep {
  step: number;
  tool: string;
  input: unknown;
  ok: boolean;
  /** Why the action was refused or failed. */
  error?: string;
  /** Page URL after the step. */
  url: string | null;
}

export type AgentRunStatus =
  /** Claude called finish with status "completed". */
  | 'completed'
  /** Claude called finish with status "failed", or the tab was lost. */
  | 'failed'
  /** maxSteps model calls without finish. */
  | 'max_steps'
  /** The model declined (stop_reason "refusal"). */
  | 'refused'
  /** The model stopped without calling finish, or its output was cut off. */
  | 'stopped';

export interface AgentRunResult {
  status: AgentRunStatus;
  summary: string | null;
  finalUrl: string | null;
  steps: AgentStep[];
  modelCalls: number;
  usage: { inputTokens: number; outputTokens: number; cacheReadInputTokens: number; cacheCreationInputTokens: number };
}

const CONTEXT_MANAGEMENT_BETA = 'context-management-2025-06-27';
const FALLBACK_BETA = 'server-side-fallback-2026-07-01';

/** Stream each request (inputs can be large) and retry a turn whose tool input was unparseable JSON. */
export function streamingCreateMessage(anthropic: Anthropic, maxJsonRetries = 2): CreateMessage {
  return async (params) => {
    for (let attempt = 0; ; attempt += 1) {
      try {
        return await anthropic.beta.messages.stream(params).finalMessage();
      } catch (error) {
        // API errors (auth, rate limit, ...) are not JSON problems; the SDK already retried them.
        if (error instanceof Anthropic.APIError || attempt >= maxJsonRetries) throw error;
      }
    }
  };
}

export class BrowserAgent {
  private readonly browser: BrowserPort;
  private readonly createMessage: CreateMessage;
  private readonly model: string;
  private readonly effort: Effort;
  private readonly maxSteps: number;
  private readonly maxTokens: number;
  private readonly beforeAction: BrowserAgentOptions['beforeAction'];
  private readonly onStep: BrowserAgentOptions['onStep'];

  constructor(options: BrowserAgentOptions) {
    this.browser = options.browser;
    this.createMessage = options.createMessage ?? streamingCreateMessage(options.anthropic ?? new Anthropic());
    this.model = options.model ?? DEFAULT_AGENT_MODEL;
    this.effort = options.effort ?? 'high';
    this.maxSteps = options.maxSteps ?? 25;
    this.maxTokens = options.maxTokens ?? 64_000;
    this.beforeAction = options.beforeAction;
    this.onStep = options.onStep;
  }

  async run(task: BrowserTask): Promise<AgentRunResult> {
    let tabId = task.tabId;
    const ownsTab = !tabId;
    if (!tabId) {
      tabId = (await this.browser.createTab({ sessionKey: task.sessionKey ?? 'browser-agent', url: task.startUrl })).tabId;
    }
    try {
      return await new AgentRun(this, tabId).execute(task.task);
    } finally {
      if (ownsTab) await this.browser.closeTab(tabId).catch(() => undefined);
    }
  }

  /** @internal */ get deps() {
    return {
      browser: this.browser,
      createMessage: this.createMessage,
      beforeAction: this.beforeAction,
      onStep: this.onStep,
      maxSteps: this.maxSteps,
      params: (messages: Anthropic.Beta.BetaMessageParam[]): MessageParams => ({
        model: this.model,
        max_tokens: this.maxTokens,
        system: BROWSER_AGENT_SYSTEM_PROMPT,
        tools: BROWSER_TOOLS,
        // One action per turn: every action invalidates the refs a second call would use.
        tool_choice: { type: 'auto', disable_parallel_tool_use: true },
        thinking: { type: 'adaptive' },
        output_config: { effort: this.effort },
        // Caches the growing, append-only prefix (tools + system + history).
        cache_control: { type: 'ephemeral' },
        // Snapshots are large; once the input passes 50k tokens, clear all but
        // the last three tool results server-side. This is not a history edit,
        // so thinking blocks stay valid.
        context_management: {
          edits: [
            {
              type: 'clear_tool_uses_20250919',
              trigger: { type: 'input_tokens', value: 50_000 },
              keep: { type: 'tool_uses', value: 3 },
            },
          ],
        },
        // On a refusal the API re-runs the turn on a fallback model chosen by refusal category.
        fallbacks: 'default',
        betas: [CONTEXT_MANAGEMENT_BETA, FALLBACK_BETA],
        messages,
      }),
    };
  }
}

/** State of one run: the conversation, the current snapshot and its refs. */
class AgentRun {
  private readonly deps: BrowserAgent['deps'];
  private readonly messages: Anthropic.Beta.BetaMessageParam[] = [];
  private readonly steps: AgentStep[] = [];
  private readonly usage = { inputTokens: 0, outputTokens: 0, cacheReadInputTokens: 0, cacheCreationInputTokens: 0 };
  private page: CrawlPage | null = null;
  private validRefs = new Set<string>();
  private nextOffset: number | null = null;

  constructor(agent: BrowserAgent, private readonly tabId: string) {
    this.deps = agent.deps;
  }

  async execute(task: string): Promise<AgentRunResult> {
    this.messages.push({ role: 'user', content: initialUserMessage(task, await this.freshSnapshot()) });

    for (let call = 1; call <= this.deps.maxSteps; call += 1) {
      const response = await this.deps.createMessage(this.deps.params(this.messages));
      this.countUsage(response.usage);
      // Append the whole content (thinking, fallback and tool_use blocks included), unchanged.
      this.messages.push({ role: 'assistant', content: response.content });

      if (response.stop_reason === 'refusal') {
        const details = response.stop_details;
        return this.result('refused', details?.explanation ?? `declined (${details?.category ?? 'no category'})`, call);
      }
      const toolUses = response.content.filter((b): b is Anthropic.Beta.BetaToolUseBlock => b.type === 'tool_use');
      if (response.stop_reason === 'max_tokens' || response.stop_reason === 'model_context_window_exceeded') {
        // A tool input cut off here can still parse as a valid partial object; never run it.
        return this.result('stopped', `model output cut off (${response.stop_reason})`, call);
      }
      if (toolUses.length === 0) {
        const text = response.content.flatMap((b) => (b.type === 'text' ? [b.text] : [])).join('\n').trim();
        return this.result('stopped', text || null, call);
      }

      const results: Anthropic.Beta.BetaToolResultBlockParam[] = [];
      let acted = false;
      for (const use of toolUses) {
        if (acted) {
          results.push(errorResult(use.id, 'Skipped: only one action per turn. Read the new snapshot first.'));
          continue;
        }
        const outcome = await this.runTool(call, use);
        if (outcome.finish) return this.result(outcome.finish.status, outcome.finish.summary, call);
        if (outcome.lostTab) return this.result('failed', outcome.lostTab, call);
        results.push(outcome.result);
        acted = true;
      }
      this.messages.push({ role: 'user', content: results });
    }
    return this.result('max_steps', null, this.deps.maxSteps);
  }

  private async runTool(
    step: number,
    use: Anthropic.Beta.BetaToolUseBlock,
  ): Promise<{
    result: Anthropic.Beta.BetaToolResultBlockParam;
    finish?: { status: 'completed' | 'failed'; summary: string };
    lostTab?: string;
  }> {
    const record = (ok: boolean, error?: string) => {
      const entry: AgentStep = { step, tool: use.name, input: use.input, ok, error, url: this.page?.url ?? null };
      this.steps.push(entry);
      this.deps.onStep?.(entry);
    };
    const refuse = (message: string) => {
      record(false, message);
      return { result: errorResult(use.id, message) };
    };

    const action = parseAction(use.name, use.input);
    if ('error' in action) return refuse(action.error);

    if (action.kind === 'finish') {
      record(true);
      return { result: okResult(use.id, 'Finished.'), finish: { status: action.status, summary: action.summary } };
    }

    if (action.kind === 'read_more') {
      if (this.nextOffset === null) return refuse('The current snapshot is complete; there is nothing more to read.');
      const block = await this.snapshotWindow(this.nextOffset);
      record(true);
      return { result: okResult(use.id, block) };
    }

    if ((action.kind === 'click' || action.kind === 'type_text') && !this.validRefs.has(action.ref)) {
      return refuse(
        `Ref ${action.ref} is not in the latest snapshot. Use only refs that appear in the most recent <page_snapshot>.`,
      );
    }
    if (this.deps.beforeAction && this.page && !(await this.deps.beforeAction(action, this.page))) {
      return refuse('The operator declined this action. Choose another way, or finish with status "failed".');
    }

    try {
      if (action.kind === 'click') await this.deps.browser.click(this.tabId, action.ref);
      else if (action.kind === 'type_text') {
        await this.deps.browser.type(this.tabId, action.ref, action.text, { clear: action.clear, submit: action.pressEnter });
      } else if ('url' in action) await this.deps.browser.navigate(this.tabId, action.url);
      else await this.deps.browser.navigate(this.tabId, { macro: action.macro, query: action.query });
    } catch (error) {
      if (!(error instanceof CamofoxError)) throw error;
      if (error.needsNewTab) {
        record(false, error.message);
        return { result: errorResult(use.id, error.message), lostTab: `the browser tab was lost: ${error.message}` };
      }
      // Stale refs, a bad target, a timeout: show Claude what the page looks like now.
      const message = error.needsFreshSnapshot
        ? 'The page changed before the action ran, so it was not performed. Here is the page now; pick a ref from it.'
        : `The action failed: ${error.message}. Here is the page now.`;
      record(false, error.message);
      return { result: errorResult(use.id, `${message}\n\n${await this.freshSnapshot()}`) };
    }

    const block = await this.freshSnapshot();
    record(true);
    return { result: okResult(use.id, `Done. The page now:\n\n${block}`) };
  }

  /** Snapshot from the top; retires every earlier ref. */
  private async freshSnapshot(): Promise<string> {
    const response = await this.deps.browser.snapshot(this.tabId);
    this.validRefs = new Set();
    return this.absorb(response);
  }

  /** A later window of the same snapshot; earlier refs stay valid (the server serves them from one cached snapshot). */
  private async snapshotWindow(offset: number): Promise<string> {
    return this.absorb(await this.deps.browser.snapshot(this.tabId, { offset }));
  }

  private absorb(response: SnapshotResponse): string {
    const page = parseSnapshot(response);
    this.page = page;
    for (const element of page.interactive) this.validRefs.add(element.ref);
    this.nextOffset = page.completeness.hasMore ? page.completeness.nextOffset : null;
    return formatSnapshot(response);
  }

  private countUsage(usage: Anthropic.Beta.BetaUsage): void {
    this.usage.inputTokens += usage.input_tokens;
    this.usage.outputTokens += usage.output_tokens;
    this.usage.cacheReadInputTokens += usage.cache_read_input_tokens ?? 0;
    this.usage.cacheCreationInputTokens += usage.cache_creation_input_tokens ?? 0;
  }

  private result(status: AgentRunStatus, summary: string | null, modelCalls: number): AgentRunResult {
    return { status, summary, finalUrl: this.page?.url ?? null, steps: this.steps, modelCalls, usage: { ...this.usage } };
  }
}

/** Wrap a snapshot in tags the system prompt marks as untrusted page content. */
export function formatSnapshot(response: SnapshotResponse): string {
  const attrs = [`url="${escapeAttr(response.url)}"`];
  if (response.truncated) {
    attrs.push('truncated="true"');
    if (response.hasMore && response.nextOffset != null) attrs.push('more="call read_more"');
  }
  // A page cannot close the tag early by printing it.
  const body = (response.snapshot || '(empty page)').replace(/<\/?page_snapshot/gi, (m) => m.replace('<', '&lt;'));
  return `<page_snapshot ${attrs.join(' ')}>\n${body}\n</page_snapshot>`;
}

function escapeAttr(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

function okResult(id: string, content: string): Anthropic.Beta.BetaToolResultBlockParam {
  return { type: 'tool_result', tool_use_id: id, content };
}

function errorResult(id: string, content: string): Anthropic.Beta.BetaToolResultBlockParam {
  return { type: 'tool_result', tool_use_id: id, content, is_error: true };
}
