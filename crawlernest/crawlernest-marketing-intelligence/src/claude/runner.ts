/**
 * A `SkillRunner` that runs a NotFair or Claude Ads skill as a Claude tool-use loop.
 *
 *   SKILL.md + policy (system) → Claude reads data with read-only tools and the
 *   skill's own reference files → Claude calls submit_findings → the input of
 *   that call is the runner's result, which the engine parses into a 4-state report
 *
 * The agent never holds a write tool. The host supplies reads only (checked by
 * name at construction); a `MutationBlockedError` thrown by one of them aborts the
 * run, and the engine records it as a policy violation. The conversation is
 * append-only (thinking blocks are bound to it); old tool results are cleared
 * server-side by context editing, not by rewriting history.
 */
import path from 'node:path';

import Anthropic from '@anthropic-ai/sdk';

import { MutationBlockedError } from '../safety.js';
import type { RoutedTask, SkillRunRequest, SkillRunner } from '../types.js';
import { initialUserMessage, systemPrompt } from './prompt.js';
import {
  READ_SKILL_FILE_TOOL,
  ReadToolError,
  SUBMIT_TOOL,
  asObject,
  assertReadTools,
  buildTools,
  readSkillFile,
  validateSubmission,
} from './tools.js';
import type { ReadTool } from './tools.js';

export const DEFAULT_SKILL_MODEL = 'claude-opus-5-5';

export type MessageParams = Anthropic.Beta.Messages.MessageCreateParamsNonStreaming;
export type CreateMessage = (params: MessageParams) => Promise<Anthropic.Beta.BetaMessage>;
export type Effort = 'low' | 'medium' | 'high' | 'xhigh' | 'max';

export interface SkillRunStep {
  skillId: string;
  modelCall: number;
  tool: string;
  input: unknown;
  ok: boolean;
  error?: string;
}

export interface SkillRunUsage {
  inputTokens: number;
  outputTokens: number;
  cacheReadInputTokens: number;
  cacheCreationInputTokens: number;
}

export type SkillRunOutcome = 'submitted' | 'text_only' | 'refused' | 'cut_off' | 'max_steps' | 'blocked_write';

export interface SkillRunSummary {
  skillId: string;
  outcome: SkillRunOutcome;
  modelCalls: number;
  usage: SkillRunUsage;
}

export interface ClaudeSkillRunnerOptions {
  /** Every read the host offers. By default a run gets the ones whose platform is in the task's scope. */
  tools?: readonly ReadTool[];
  /** Chooses the tools for one task instead of the platform filter. */
  toolsFor?: (task: RoutedTask, tools: readonly ReadTool[]) => readonly ReadTool[];
  /** Used to build the default createMessage. Defaults to `new Anthropic()` (ANTHROPIC_API_KEY or an `ant auth` profile). */
  anthropic?: Anthropic;
  /** Replaces the API call; for tests or a custom transport. */
  createMessage?: CreateMessage;
  model?: string;
  /** Default "high": audits are multi-step tool use, and Opus 5.5 would otherwise default to "medium". */
  effort?: Effort;
  /** Model calls before the run is stopped. Default 30. */
  maxSteps?: number;
  /** Per-response output cap. Default 64 000 (the runner streams). */
  maxTokens?: number;
  /** The folder `read_skill_file` may read. Default: the library root, two levels above the skill folder. */
  libraryRootFor?: (skillPath: string) => string;
  /** Characters of one tool result sent to Claude before it is cut, with a note saying so. Default 100 000. */
  maxResultChars?: number;
  onStep?: (step: SkillRunStep) => void;
  onRunComplete?: (summary: SkillRunSummary) => void;
}

/** Why a run produced no result. The engine turns it into a `failed` report. */
export class SkillRunError extends Error {
  constructor(
    readonly outcome: SkillRunOutcome,
    message: string,
  ) {
    super(message);
    this.name = 'SkillRunError';
  }
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

function defaultLibraryRoot(skillPath: string): string {
  // <library>/skills/<name>/SKILL.md
  return path.resolve(path.dirname(skillPath), '..', '..');
}

export class ClaudeSkillRunner implements SkillRunner {
  private readonly tools: readonly ReadTool[];
  private readonly toolsFor: NonNullable<ClaudeSkillRunnerOptions['toolsFor']>;
  private readonly createMessage: CreateMessage;
  private readonly model: string;
  private readonly effort: Effort;
  private readonly maxSteps: number;
  private readonly maxTokens: number;
  private readonly libraryRootFor: (skillPath: string) => string;
  private readonly maxResultChars: number;
  private readonly onStep: ClaudeSkillRunnerOptions['onStep'];
  private readonly onRunComplete: ClaudeSkillRunnerOptions['onRunComplete'];

  constructor(options: ClaudeSkillRunnerOptions = {}) {
    this.tools = options.tools ?? [];
    assertReadTools(this.tools);
    this.toolsFor = options.toolsFor ?? ((task, tools) => tools.filter((tool) => task.platforms.includes(tool.platform)));
    this.createMessage = options.createMessage ?? streamingCreateMessage(options.anthropic ?? new Anthropic());
    this.model = options.model ?? DEFAULT_SKILL_MODEL;
    this.effort = options.effort ?? 'high';
    this.maxSteps = options.maxSteps ?? 30;
    this.maxTokens = options.maxTokens ?? 64_000;
    this.libraryRootFor = options.libraryRootFor ?? defaultLibraryRoot;
    this.maxResultChars = options.maxResultChars ?? 100_000;
    this.onStep = options.onStep;
    this.onRunComplete = options.onRunComplete;
  }

  async run(request: SkillRunRequest): Promise<unknown> {
    if (request.policy.allowMutations !== false) throw new Error('Refusing a run whose policy allows mutations.');
    const readTools = this.toolsFor(request.task, this.tools);
    assertReadTools(readTools);
    return new SkillRun(this, request, readTools).execute();
  }

  /** @internal */ get deps() {
    return {
      createMessage: this.createMessage,
      maxSteps: this.maxSteps,
      maxResultChars: this.maxResultChars,
      libraryRootFor: this.libraryRootFor,
      onStep: this.onStep,
      onRunComplete: this.onRunComplete,
      params: (
        system: string,
        tools: Anthropic.Beta.BetaTool[],
        messages: Anthropic.Beta.BetaMessageParam[],
      ): MessageParams => ({
        model: this.model,
        max_tokens: this.maxTokens,
        system,
        tools,
        tool_choice: { type: 'auto' },
        thinking: { type: 'adaptive' },
        output_config: { effort: this.effort },
        // Caches the growing, append-only prefix (tools + system + history).
        cache_control: { type: 'ephemeral' },
        // Reports can be large; past 80k input tokens, clear all but the last five tool results server-side.
        context_management: {
          edits: [
            {
              type: 'clear_tool_uses_20250919',
              trigger: { type: 'input_tokens', value: 80_000 },
              keep: { type: 'tool_uses', value: 5 },
              // The skill's own instructions stay readable for the whole run.
              exclude_tools: [READ_SKILL_FILE_TOOL],
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

/** State of one run: the conversation and its usage. */
class SkillRun {
  private readonly deps: ClaudeSkillRunner['deps'];
  private readonly messages: Anthropic.Beta.BetaMessageParam[] = [];
  private readonly usage: SkillRunUsage = { inputTokens: 0, outputTokens: 0, cacheReadInputTokens: 0, cacheCreationInputTokens: 0 };
  private readonly system: string;
  private readonly tools: Anthropic.Beta.BetaTool[];
  private readonly byName: Map<string, ReadTool>;
  private modelCalls = 0;

  constructor(
    runner: ClaudeSkillRunner,
    private readonly request: SkillRunRequest,
    readTools: readonly ReadTool[],
  ) {
    this.deps = runner.deps;
    this.system = systemPrompt(request, readTools);
    this.tools = buildTools(readTools, request.task.access);
    this.byName = new Map(readTools.map((tool) => [tool.name, tool]));
  }

  async execute(): Promise<unknown> {
    this.messages.push({ role: 'user', content: initialUserMessage(this.request) });

    for (let call = 1; call <= this.deps.maxSteps; call += 1) {
      this.modelCalls = call;
      const response = await this.deps.createMessage(this.deps.params(this.system, this.tools, this.messages));
      this.countUsage(response.usage);
      // Append the whole content (thinking, fallback and tool_use blocks included), unchanged.
      this.messages.push({ role: 'assistant', content: response.content });

      if (response.stop_reason === 'refusal') {
        const details = response.stop_details;
        this.fail('refused', `the model declined: ${details?.explanation ?? details?.category ?? 'no explanation'}`);
      }
      if (response.stop_reason === 'max_tokens' || response.stop_reason === 'model_context_window_exceeded') {
        // A tool input cut off here can still parse as a valid partial object; never run it.
        this.fail('cut_off', `the model output was cut off (${response.stop_reason})`);
      }

      const toolUses = response.content.filter((b): b is Anthropic.Beta.BetaToolUseBlock => b.type === 'tool_use');
      if (toolUses.length === 0) {
        // No submit: hand any text to the parser, which reads JSON or a checklist and marks the rest failed.
        const text = response.content.flatMap((b) => (b.type === 'text' ? [b.text] : [])).join('\n').trim();
        if (!text) this.fail('text_only', 'the model stopped without calling submit_findings');
        this.complete('text_only');
        return text;
      }

      const submit = toolUses.find((use) => use.name === SUBMIT_TOOL);
      const submission = submit ? validateSubmission(submit.input, this.request.task.access) : undefined;
      if (submit && submission) {
        this.record(call, submit, submission.ok, submission.ok ? undefined : submission.error);
        if (submission.ok) {
          this.complete('submitted');
          return submission.value;
        }
      }

      // Reads are independent: run them together and answer them in one message.
      const results = await Promise.all(
        toolUses.map((use) =>
          use === submit && submission && !submission.ok
            ? errorResult(use.id, `${submission.error}. Fix it and call ${SUBMIT_TOOL} again.`)
            : this.runTool(call, use),
        ),
      );
      this.messages.push({ role: 'user', content: results });
    }
    this.fail('max_steps', `no result after ${this.deps.maxSteps} model calls`);
  }

  private async runTool(call: number, use: Anthropic.Beta.BetaToolUseBlock): Promise<Anthropic.Beta.BetaToolResultBlockParam> {
    const checked = asObject(use.input);
    if (!checked.ok) {
      this.record(call, use, false, checked.error);
      return errorResult(use.id, checked.error);
    }
    const args = checked.value;

    try {
      if (use.name === READ_SKILL_FILE_TOOL) {
        const relative = args.path;
        if (typeof relative !== 'string' || !relative) throw new ReadToolError('path is required');
        const { skill } = this.request;
        const text = await readSkillFile(skill.path, this.deps.libraryRootFor(skill.path), relative);
        this.record(call, use, true);
        return okResult(use.id, wrapData(`${READ_SKILL_FILE_TOOL} ${relative}`, text, this.deps.maxResultChars));
      }

      const tool = this.byName.get(use.name);
      if (!tool) throw new ReadToolError(`Unknown tool ${JSON.stringify(use.name)}.`);
      const data = await tool.run(args);
      this.record(call, use, true);
      const body = typeof data === 'string' ? data : JSON.stringify(data, null, 1) ?? 'null';
      return okResult(use.id, wrapData(use.name, body, this.deps.maxResultChars));
    } catch (error) {
      if (error instanceof MutationBlockedError) {
        // A read tool that tried to write is a host bug, not something to work around: stop the run.
        this.record(call, use, false, error.message);
        this.complete('blocked_write');
        throw error;
      }
      if (error instanceof Anthropic.APIError) throw error;
      const message = error instanceof Error ? error.message : String(error);
      this.record(call, use, false, message);
      return errorResult(use.id, `The tool failed: ${message}. Report checks that depend on it as unknown if you cannot get the data another way.`);
    }
  }

  private record(modelCall: number, use: Anthropic.Beta.BetaToolUseBlock, ok: boolean, error?: string): void {
    this.deps.onStep?.({ skillId: this.request.task.skillId, modelCall, tool: use.name, input: use.input, ok, error });
  }

  private countUsage(usage: Anthropic.Beta.BetaUsage): void {
    this.usage.inputTokens += usage.input_tokens;
    this.usage.outputTokens += usage.output_tokens;
    this.usage.cacheReadInputTokens += usage.cache_read_input_tokens ?? 0;
    this.usage.cacheCreationInputTokens += usage.cache_creation_input_tokens ?? 0;
  }

  private complete(outcome: SkillRunOutcome): void {
    this.deps.onRunComplete?.({ skillId: this.request.task.skillId, outcome, modelCalls: this.modelCalls, usage: { ...this.usage } });
  }

  private fail(outcome: SkillRunOutcome, message: string): never {
    this.complete(outcome);
    throw new SkillRunError(outcome, `${this.request.task.command}: ${message}`);
  }
}

/** Wraps data in tags the system prompt marks as untrusted, and says so when it had to be cut. */
export function wrapData(label: string, body: string, maxChars: number): string {
  const cut = body.length > maxChars;
  const shown = (cut ? body.slice(0, maxChars) : body).replace(/<\/?tool_result_data/gi, (m) => m.replace('<', '&lt;'));
  const note = cut
    ? `\n[Cut at ${maxChars} of ${body.length} characters. Narrow the query (date range, fields, filters) to see the rest; do not treat the missing part as empty.]`
    : '';
  return `<tool_result_data source="${label.replace(/"/g, '&quot;')}">\n${shown}\n</tool_result_data>${note}`;
}

function okResult(id: string, content: string): Anthropic.Beta.BetaToolResultBlockParam {
  return { type: 'tool_result', tool_use_id: id, content };
}

function errorResult(id: string, content: string): Anthropic.Beta.BetaToolResultBlockParam {
  return { type: 'tool_result', tool_use_id: id, content, is_error: true };
}
