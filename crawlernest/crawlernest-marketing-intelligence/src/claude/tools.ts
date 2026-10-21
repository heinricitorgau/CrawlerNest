import { realpath, readFile } from 'node:fs/promises';
import path from 'node:path';

import type Anthropic from '@anthropic-ai/sdk';

import { isReadOperation } from '../safety.js';
import type { AccessMode, Platform } from '../types.js';

/**
 * A read the host lets the agent make: a GA4 report, a Google Ads GAQL search, a
 * Search Console query. The host owns the credentials and the client; build `run`
 * on a client wrapped with `guardPlatformClient` so a write cannot slip through it.
 */
export interface ReadTool {
  /** What Claude calls. Must start with a read verb (`get_`, `list_`, `search_`, `query_`, …). */
  name: string;
  description: string;
  platform: Platform;
  inputSchema: Anthropic.Beta.BetaTool.InputSchema;
  run(input: Record<string, unknown>): Promise<unknown>;
}

export const SUBMIT_TOOL = 'submit_findings';
export const READ_SKILL_FILE_TOOL = 'read_skill_file';
const RESERVED = new Set([SUBMIT_TOOL, READ_SKILL_FILE_TOOL]);

export class ReadToolError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ReadToolError';
  }
}

/** Refuses a tool whose name is not a read, or that collides with the runner's own tools. */
export function assertReadTools(tools: readonly ReadTool[]): void {
  const seen = new Set<string>();
  for (const tool of tools) {
    if (!/^[a-zA-Z0-9_-]{1,64}$/.test(tool.name)) throw new ReadToolError(`Tool name ${JSON.stringify(tool.name)} is not a valid tool name.`);
    if (RESERVED.has(tool.name)) throw new ReadToolError(`Tool name ${tool.name} is reserved by the runner.`);
    if (!isReadOperation(tool.name)) {
      throw new ReadToolError(`Tool ${tool.name} is not named as a read (get_, list_, search_, query_, …); only reads may be given to the agent.`);
    }
    if (seen.has(tool.name)) throw new ReadToolError(`Tool ${tool.name} is defined twice.`);
    seen.add(tool.name);
  }
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

const EVIDENCE_SCHEMA = {
  type: 'object',
  properties: {
    source: { type: 'string', description: 'Which tool or source the evidence came from, e.g. "search_google_ads".' },
    detail: { type: 'string', description: 'The observed value or fact, copied from the tool result.' },
    reference: { type: 'string', description: 'Query, resource name, report or URL that reproduces it.' },
  },
  required: ['source', 'detail'],
  additionalProperties: false,
} as const;

const FINDING_SCHEMA = {
  type: 'object',
  properties: {
    id: { type: 'string', description: 'The skill’s control or check id when it has one, e.g. "G-CT-01".' },
    title: { type: 'string' },
    status: { type: 'string', enum: ['pass', 'fail', 'unknown', 'not_applicable'] },
    severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'info'] },
    confidence: { type: 'string', enum: ['high', 'medium', 'low', 'none'] },
    observation: { type: 'string', description: 'What the data shows.' },
    diagnosis: { type: 'string', description: 'Why it matters, or for unknown/not_applicable, why it could not be judged or does not apply.' },
    recommendation: { type: 'string', description: 'What a person should do about it.' },
    evidence: { type: 'array', items: EVIDENCE_SCHEMA },
  },
  required: ['id', 'title', 'status', 'severity', 'observation', 'evidence'],
  additionalProperties: false,
} as const;

const PROPOSAL_SCHEMA = {
  type: 'object',
  properties: {
    platform: { type: 'string', enum: ['google_ads', 'meta_ads', 'youtube_ads', 'linkedin_ads', 'tiktok_ads', 'microsoft_ads', 'search_console', 'ga4', 'website'] },
    target: { type: 'string', description: 'The finding id this fixes, or the campaign / ad group / property / page it is about.' },
    summary: { type: 'string', description: 'The change, in one sentence, as a proposal ("Lower the tCPA of campaign 42 by 10%").' },
    change: { type: 'object', description: 'The fields and values that would change.' },
    rationale: { type: 'string' },
  },
  required: ['platform', 'target', 'summary', 'rationale'],
  additionalProperties: false,
} as const;

function submitTool(access: AccessMode): Anthropic.Beta.BetaTool {
  const properties: Record<string, unknown> = {
    findings: { type: 'array', items: FINDING_SCHEMA },
    missing_inputs: { type: 'array', items: { type: 'string' }, description: 'Data the skill needed and did not have.' },
  };
  if (access === 'draft_only') {
    properties.proposed_changes = { type: 'array', items: PROPOSAL_SCHEMA, description: 'Drafts only. Nothing here is applied.' };
  }
  return {
    name: SUBMIT_TOOL,
    description:
      'Deliver the result of the skill and end the run. Call it exactly once, after you have gathered the evidence. ' +
      'Every pass or fail must carry evidence copied from tool results; a check you could not judge is unknown.',
    eager_input_streaming: true,
    input_schema: { type: 'object', properties, required: ['findings'], additionalProperties: false },
  };
}

const READ_SKILL_FILE: Anthropic.Beta.BetaTool = {
  name: READ_SKILL_FILE_TOOL,
  description:
    'Read a file the skill instructions refer to (a WORKFLOW.md, a reference, a checklist). The path is resolved ' +
    'relative to the skill’s SKILL.md, as written in the instructions. Only text files inside the skill library can be read.',
  eager_input_streaming: true,
  input_schema: {
    type: 'object',
    properties: { path: { type: 'string', description: 'Relative path as written in the instructions, e.g. "../../seo/seo-analysis/WORKFLOW.md".' } },
    required: ['path'],
    additionalProperties: false,
  },
};

/**
 * The tools for one run, in a fixed order: they are part of the cache prefix and of
 * what thinking blocks are bound to, so they must not change during the run.
 */
export function buildTools(readTools: readonly ReadTool[], access: AccessMode): Anthropic.Beta.BetaTool[] {
  return [
    ...readTools.map((tool) => ({
      name: tool.name,
      description: `[read-only, ${tool.platform}] ${tool.description}`,
      eager_input_streaming: true,
      input_schema: tool.inputSchema,
    })),
    READ_SKILL_FILE,
    submitTool(access),
  ];
}

// ---------------------------------------------------------------------------
// Input validation (eager_input_streaming turns off server-side validation)
// ---------------------------------------------------------------------------

export type Checked<T> = { ok: true; value: T } | { ok: false; error: string };

export function asObject(input: unknown): Checked<Record<string, unknown>> {
  if (typeof input !== 'object' || input === null || Array.isArray(input)) {
    return { ok: false, error: `INVALID_JSON: the tool input must be a JSON object, got ${JSON.stringify(input)}` };
  }
  return { ok: true, value: input as Record<string, unknown> };
}

const STATUSES = new Set(['pass', 'fail', 'unknown', 'not_applicable']);

/** Checks a submit_findings input enough that the parser gets what the schema promised. */
export function validateSubmission(input: unknown, access: AccessMode): Checked<Record<string, unknown>> {
  const checked = asObject(input);
  if (!checked.ok) return checked;
  const args = checked.value;
  const fail = (error: string): Checked<Record<string, unknown>> => ({ ok: false, error });
  if (!Array.isArray(args.findings)) return fail('findings must be an array');
  for (const [index, finding] of args.findings.entries()) {
    const item = asObject(finding);
    if (!item.ok) return fail(`findings[${index}]: ${item.error}`);
    const f = item.value;
    if (typeof f.id !== 'string' || typeof f.title !== 'string') return fail(`findings[${index}] needs string id and title`);
    if (typeof f.status !== 'string' || !STATUSES.has(f.status)) {
      return fail(`findings[${index}].status must be one of pass, fail, unknown, not_applicable`);
    }
    if (!Array.isArray(f.evidence)) return fail(`findings[${index}].evidence must be an array (empty for unknown or not_applicable)`);
  }
  if (args.proposed_changes !== undefined) {
    if (access !== 'draft_only') return fail('This task is read-only: leave out proposed_changes and put advice in recommendation.');
    if (!Array.isArray(args.proposed_changes)) return fail('proposed_changes must be an array');
  }
  return checked;
}

// ---------------------------------------------------------------------------
// Reading skill files
// ---------------------------------------------------------------------------

const TEXT_EXTENSIONS = new Set(['.md', '.txt', '.json', '.yaml', '.yml', '.csv']);
export const MAX_SKILL_FILE_CHARS = 200_000;

/**
 * Reads `relative` against the SKILL.md directory, refusing anything that resolves
 * (symlinks included) outside `libraryRoot` or is not a text file.
 */
export async function readSkillFile(skillPath: string, libraryRoot: string, relative: string): Promise<string> {
  if (path.isAbsolute(relative)) throw new ReadToolError('Give a path relative to SKILL.md, not an absolute one.');
  const root = await realpath(libraryRoot);
  let resolved: string;
  try {
    resolved = await realpath(path.resolve(path.dirname(skillPath), relative));
  } catch {
    throw new ReadToolError(`No such file: ${relative}`);
  }
  if (resolved !== root && !resolved.startsWith(root + path.sep)) {
    throw new ReadToolError(`${relative} is outside the skill library.`);
  }
  if (!TEXT_EXTENSIONS.has(path.extname(resolved).toLowerCase())) {
    throw new ReadToolError(`${relative} is not a text file this tool reads (${[...TEXT_EXTENSIONS].join(', ')}).`);
  }
  const text = await readFile(resolved, 'utf8');
  return text.length > MAX_SKILL_FILE_CHARS
    ? `${text.slice(0, MAX_SKILL_FILE_CHARS)}\n\n[The file continues; only the first ${MAX_SKILL_FILE_CHARS} characters are shown.]`
    : text;
}
