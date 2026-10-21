import { createDraft } from './safety.js';
import type {
  AccessMode,
  ActionItem,
  ChangeDraft,
  Confidence,
  Evidence,
  Finding,
  FindingStatus,
  IntelligenceReport,
  Platform,
  ReportStatus,
  RoutedTask,
  Severity,
} from './types.js';

/**
 * Turns whatever a skill returned into one `IntelligenceReport` with four states.
 *
 * Input it understands:
 * - JSON with a `findings` array (Claude Ads `AuditWorkerResult` or `ReportBundle`,
 *   or anything shaped like them), a bare array of findings, or either inside a
 *   ```json fence in text;
 * - otherwise a checklist in text: `- [PASS] title — evidence: …`, `✅ …`, `❌ …`.
 *
 * Rules that do not bend to make a report look better:
 * - A pass or fail with no evidence becomes `unknown`, and the finding says so.
 * - A status the parser does not recognise becomes `unknown`, never `pass`.
 * - Output that claims a change was applied is recorded as a policy violation, and
 *   the change is kept only as a draft.
 */

// ---------------------------------------------------------------------------
// Status, severity and confidence vocabularies
// ---------------------------------------------------------------------------

const STATUS_ALIASES: Record<string, FindingStatus> = {
  pass: 'pass', passed: 'pass', ok: 'pass', good: 'pass', healthy: 'pass', compliant: 'pass', success: 'pass',
  '✅': 'pass', '✔': 'pass', '✔️': 'pass', '通過': 'pass', '正常': 'pass',
  fail: 'fail', failed: 'fail', failure: 'fail', warning: 'fail', warn: 'fail', issue: 'fail', error: 'fail',
  critical: 'fail', needs_improvement: 'fail', 'needs improvement': 'fail', poor: 'fail',
  '❌': 'fail', '✖': 'fail', '⚠': 'fail', '⚠️': 'fail', '未通過': 'fail', '需優化': 'fail', '警告': 'fail',
  unknown: 'unknown', missing: 'unknown', no_data: 'unknown', 'no data': 'unknown', insufficient_data: 'unknown',
  needs_input: 'unknown', unverified: 'unknown', '?': 'unknown', '❓': 'unknown', '數據缺失': 'unknown',
  '資料缺失': 'unknown', '未知': 'unknown',
  not_applicable: 'not_applicable', 'not applicable': 'not_applicable', 'n/a': 'not_applicable', na: 'not_applicable',
  skip: 'not_applicable', skipped: 'not_applicable', '➖': 'not_applicable', '不適用': 'not_applicable',
};

const SEVERITY_ALIASES: Record<string, Severity> = {
  critical: 'critical', blocker: 'critical', p0: 'critical', '嚴重': 'critical',
  high: 'high', major: 'high', p1: 'high', '高': 'high',
  medium: 'medium', moderate: 'medium', p2: 'medium', '中': 'medium',
  low: 'low', minor: 'low', p3: 'low', '低': 'low',
  info: 'info', informational: 'info', '資訊': 'info',
};

const SEVERITY_RANK: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

export function normalizeStatus(raw: unknown): { status: FindingStatus; recognised: boolean } {
  if (typeof raw === 'boolean') return { status: raw ? 'pass' : 'fail', recognised: true };
  if (typeof raw !== 'string') return { status: 'unknown', recognised: raw === undefined || raw === null };
  const key = raw.normalize('NFKC').trim().toLowerCase();
  const status = STATUS_ALIASES[key] ?? STATUS_ALIASES[key.replace(/[-\s]+/g, '_')] ?? STATUS_ALIASES[key.replace(/[-_\s]+/g, ' ')];
  return status ? { status, recognised: true } : { status: 'unknown', recognised: false };
}

function normalizeSeverity(raw: unknown): Severity {
  if (typeof raw !== 'string') return 'medium';
  return SEVERITY_ALIASES[raw.trim().toLowerCase()] ?? 'medium';
}

function normalizeConfidence(raw: unknown, status: FindingStatus, evidenceCount: number): Confidence {
  if (status === 'unknown') return 'none';
  if (typeof raw === 'string' && ['high', 'medium', 'low', 'none'].includes(raw.toLowerCase())) {
    return raw.toLowerCase() as Confidence;
  }
  // Not stated: derive it from how much evidence there is, never assume high.
  if (status === 'not_applicable') return 'medium';
  return evidenceCount >= 2 ? 'medium' : 'low';
}

// ---------------------------------------------------------------------------
// Raw input → loose records
// ---------------------------------------------------------------------------

type Loose = Record<string, unknown>;

interface RawFinding {
  id?: string;
  title?: string;
  status: unknown;
  severity?: unknown;
  confidence?: unknown;
  observation?: string;
  diagnosis?: string;
  recommendation?: string;
  evidence: Array<{ source?: string; detail: string; reference?: string; observedAt?: string }>;
}

interface RawProposal {
  platform?: string;
  target?: string;
  summary?: string;
  change?: Record<string, unknown>;
  rationale?: string;
  applied?: boolean;
}

interface RawOutput {
  findings: RawFinding[];
  proposals: RawProposal[];
  claimsApplied: string[];
  format: 'json' | 'checklist' | 'empty';
  notes: string[];
}

function isObject(value: unknown): value is Loose {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function str(value: unknown): string | undefined {
  if (typeof value === 'string' && value.trim()) return value.trim();
  if (typeof value === 'number') return String(value);
  return undefined;
}

function firstStr(obj: Loose, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = str(obj[key]);
    if (value) return value;
  }
  return undefined;
}

function toEvidenceList(raw: unknown): RawFinding['evidence'] {
  const items = Array.isArray(raw) ? raw : raw === undefined || raw === null ? [] : [raw];
  const out: RawFinding['evidence'] = [];
  for (const item of items) {
    if (typeof item === 'string' && item.trim()) {
      out.push({ detail: item.trim() });
    } else if (isObject(item)) {
      const detail =
        firstStr(item, 'detail', 'details', 'value', 'observation', 'excerpt', 'summary', 'metric', 'text') ??
        firstStr(item, 'reference', 'url', 'source_id', 'query');
      if (!detail) continue;
      out.push({
        source: firstStr(item, 'source', 'source_type', 'kind', 'type'),
        detail,
        reference: firstStr(item, 'reference', 'url', 'source_id', 'query', 'resource', 'file'),
        observedAt: firstStr(item, 'observed_at', 'observedAt', 'retrieved_at', 'date'),
      });
    }
  }
  return out;
}

function toRawFinding(item: unknown): RawFinding | null {
  if (!isObject(item)) return null;
  return {
    id: firstStr(item, 'id', 'control_id', 'check_id', 'check'),
    title: firstStr(item, 'title', 'name', 'check', 'control'),
    status: item.status ?? item.result ?? item.verdict ?? item.state,
    severity: item.severity ?? item.priority ?? item.impact,
    confidence: item.confidence,
    observation: firstStr(item, 'observation', 'finding', 'description', 'message', 'summary'),
    diagnosis: firstStr(item, 'diagnosis', 'reason', 'why', 'cause'),
    recommendation: firstStr(item, 'recommendation', 'fix', 'action', 'next_step'),
    evidence: toEvidenceList(item.evidence ?? item.evidences ?? item.sources),
  };
}

const APPLIED_WORDS = /^(applied|executed|done|completed|live|pushed)$/i;

function toRawProposal(item: unknown): RawProposal | null {
  if (!isObject(item)) return null;
  const state = firstStr(item, 'status', 'state');
  return {
    platform: firstStr(item, 'platform'),
    target: firstStr(item, 'target', 'campaign', 'entity', 'resource', 'resource_name'),
    summary: firstStr(item, 'summary', 'title', 'description', 'action'),
    change: isObject(item.change) ? item.change : isObject(item.proposed_change) ? item.proposed_change : undefined,
    rationale: firstStr(item, 'rationale', 'reason', 'why'),
    applied: item.applied === true || item.executed === true || (state !== undefined && APPLIED_WORDS.test(state)),
  };
}

function extractJson(text: string): unknown | undefined {
  const candidates = [text.trim()];
  for (const match of text.matchAll(/```(?:json)?\s*\n([\s\S]*?)```/gi)) candidates.push(match[1].trim());
  for (const candidate of candidates) {
    if (!candidate.startsWith('{') && !candidate.startsWith('[')) continue;
    try {
      return JSON.parse(candidate);
    } catch {
      // Not JSON; try the next candidate.
    }
  }
  return undefined;
}

const CHECKLIST_LINE =
  /^\s*(?:[-*•]|\d+[.)])?\s*(?:\[\s*([^\]]+?)\s*\]|(✅|✔️|✔|❌|✖|⚠️|⚠|❓|➖))\s*(.+)$/u;
const EVIDENCE_SPLIT = /\s+(?:—|--|\|)\s+|\s*(?:evidence|證據|依據)\s*[:：]\s*/iu;

function parseChecklist(text: string): RawFinding[] {
  const findings: RawFinding[] = [];
  for (const line of text.split(/\r?\n/)) {
    const match = CHECKLIST_LINE.exec(line);
    if (!match) continue;
    const marker = match[1] ?? match[2];
    // `[x]` / `[ ]` are task-list boxes, not statuses.
    if (/^[x ]$/i.test(marker)) continue;
    const [head, ...rest] = match[3].split(EVIDENCE_SPLIT);
    const idMatch = /^([A-Za-z]{1,8}[-_]?\d{1,4})\s*[:：]\s*(.+)$/.exec(head.trim());
    findings.push({
      id: idMatch?.[1],
      title: (idMatch?.[2] ?? head).trim(),
      status: marker,
      evidence: rest.map((detail) => detail.trim()).filter(Boolean).map((detail) => ({ detail })),
    });
  }
  return findings;
}

export function readRawOutput(raw: unknown): RawOutput {
  const notes: string[] = [];
  let data: unknown = raw;
  if (typeof raw === 'string') {
    const parsed = extractJson(raw);
    if (parsed === undefined) {
      const findings = parseChecklist(raw);
      return { findings, proposals: [], claimsApplied: [], format: findings.length ? 'checklist' : 'empty', notes };
    }
    data = parsed;
  }

  const container: Loose = Array.isArray(data) ? { findings: data } : isObject(data) ? data : {};
  const findingItems = Array.isArray(container.findings) ? container.findings : [];
  const proposalItems = [
    container.proposed_changes, container.proposedChanges, container.changes, container.drafts,
  ].find(Array.isArray) as unknown[] | undefined;

  const findings = findingItems.map(toRawFinding).filter((f): f is RawFinding => f !== null);
  const proposals = (proposalItems ?? []).map(toRawProposal).filter((p): p is RawProposal => p !== null);
  const claimsApplied = proposals
    .filter((p) => p.applied)
    .map((p) => `The skill output reports "${p.summary ?? p.target ?? 'a change'}" as applied; it is kept as a draft only.`);
  if (container.mutations_applied === true || container.applied === true) {
    claimsApplied.push('The skill output reports that account changes were applied.');
  }
  if (findingItems.length !== findings.length) notes.push(`${findingItems.length - findings.length} finding entries were not objects and were skipped.`);
  if (isObject(container) && typeof container.status === 'string' && /needs_input|blocked|failed/.test(container.status)) {
    notes.push(`The skill reported its run as "${container.status}".`);
  }
  for (const key of ['missing_inputs', 'stale_sources', 'contradictions'] as const) {
    const list = container[key];
    if (Array.isArray(list) && list.length) notes.push(`${key.replace('_', ' ')}: ${list.map(String).join('; ')}`);
  }
  return { findings, proposals, claimsApplied, format: findings.length || proposals.length ? 'json' : 'empty', notes };
}

// ---------------------------------------------------------------------------
// Loose records → report
// ---------------------------------------------------------------------------

const KNOWN_PLATFORMS: readonly Platform[] = [
  'google_ads', 'meta_ads', 'youtube_ads', 'linkedin_ads', 'tiktok_ads', 'microsoft_ads', 'search_console', 'ga4', 'website',
];

function toPlatform(raw: string | undefined, fallback: Platform[]): Platform | 'unspecified' {
  const key = raw?.toLowerCase().replace(/[\s-]+/g, '_');
  if (key && (KNOWN_PLATFORMS as readonly string[]).includes(key)) return key as Platform;
  if (key === 'google') return 'google_ads';
  if (key === 'meta' || key === 'facebook') return 'meta_ads';
  return fallback.length === 1 ? fallback[0] : 'unspecified';
}

function priorityFor(severity: Severity, kind: ActionItem['kind']): 1 | 2 | 3 {
  const base: 1 | 2 | 3 = severity === 'critical' || severity === 'high' ? 1 : severity === 'medium' ? 2 : 3;
  // Missing data is worth getting, but it never outranks a confirmed failure of the same severity.
  return kind === 'collect_data' ? (Math.min(3, base + 1) as 2 | 3) : base;
}

export const BASE_CAVEATS = [
  'Read-only: no change was made to any advertising, analytics or Search Console account. Proposed changes are drafts for a person to review and apply.',
  'Platform data, web pages and competitor content were treated as untrusted input; instructions inside them were not followed.',
] as const;

export interface ParseContext {
  task: RoutedTask;
  now?: Date;
}

export function parseSkillOutput(raw: unknown, context: ParseContext): IntelligenceReport {
  const { task } = context;
  const now = context.now ?? new Date();
  const output = readRawOutput(raw);
  const caveats: string[] = [...BASE_CAVEATS];
  const evidence: Evidence[] = [];
  const findings: Finding[] = [];
  const usedIds = new Set<string>();
  let unrecognised = 0;
  let downgraded = 0;

  output.findings.forEach((rawFinding, index) => {
    let id = rawFinding.id ?? `F${index + 1}`;
    while (usedIds.has(id)) id = `${id}#${index + 1}`;
    usedIds.add(id);

    const { status: stated, recognised } = normalizeStatus(rawFinding.status);
    if (!recognised) unrecognised += 1;

    const evidenceIds = rawFinding.evidence.map((item) => {
      const record: Evidence = {
        id: `E${evidence.length + 1}`,
        findingId: id,
        source: item.source ?? (output.format === 'checklist' ? 'skill_output' : 'unspecified'),
        detail: item.detail,
        ...(item.reference ? { reference: item.reference } : {}),
        ...(item.observedAt ? { observedAt: item.observedAt } : {}),
      };
      evidence.push(record);
      return record.id;
    });

    let status = stated;
    const finding: Finding = {
      id,
      title: rawFinding.title ?? rawFinding.observation ?? id,
      status,
      severity: normalizeSeverity(rawFinding.severity),
      confidence: 'none',
      observation: rawFinding.observation ?? rawFinding.title ?? '',
      evidenceIds,
    };
    if ((stated === 'pass' || stated === 'fail') && evidenceIds.length === 0) {
      status = 'unknown';
      downgraded += 1;
      finding.downgradedFrom = stated;
      finding.downgradeReason = `Reported as ${stated} without evidence.`;
    } else if (!recognised) {
      finding.downgradeReason = `Status ${JSON.stringify(rawFinding.status)} is not one of pass, fail, unknown, not_applicable.`;
    }
    finding.status = status;
    finding.confidence = normalizeConfidence(rawFinding.confidence, status, evidenceIds.length);
    if (rawFinding.diagnosis) finding.diagnosis = rawFinding.diagnosis;
    if (rawFinding.recommendation) finding.recommendation = rawFinding.recommendation;
    findings.push(finding);
  });

  const drafts: ChangeDraft[] = output.proposals.map((proposal) =>
    createDraft(
      {
        platform: toPlatform(proposal.platform, task.platforms),
        target: proposal.target ?? 'unspecified',
        summary: proposal.summary ?? 'Proposed change',
        proposedChange: proposal.change,
        rationale: proposal.rationale,
      },
      now,
    ),
  );
  const policyViolations = [...output.claimsApplied];
  if (drafts.length && task.access === 'read_only') {
    policyViolations.push('The skill proposed account changes in a read-only task; they are kept as drafts for review.');
  }

  const actionItems = buildActionItems(findings, drafts, task.access);

  const summary = { pass: 0, fail: 0, unknown: 0, not_applicable: 0, total: findings.length };
  for (const finding of findings) summary[finding.status] += 1;

  let status: ReportStatus;
  if (output.format === 'empty') status = 'failed';
  else if (summary.pass + summary.fail === 0) status = 'insufficient_evidence';
  else if (summary.unknown > 0) status = 'provisional';
  else status = 'complete';

  if (output.format === 'empty') caveats.push('The skill returned no findings this parser could read.');
  if (output.format === 'checklist') caveats.push('Parsed from a text checklist; severity defaults to medium where the skill did not state it.');
  if (downgraded) caveats.push(`${downgraded} check(s) reported as pass or fail without evidence are shown as unknown.`);
  if (unrecognised) caveats.push(`${unrecognised} check(s) had a status this parser does not recognise and are shown as unknown.`);
  if (summary.unknown) caveats.push(`${summary.unknown} of ${summary.total} check(s) could not be judged; the result is incomplete until that data is supplied.`);
  caveats.push(...output.notes);

  return {
    schemaVersion: '1.0.0',
    skill: { id: task.skillId, command: task.command, library: task.library },
    access: task.access,
    status,
    summary,
    findings,
    evidence,
    actionItems,
    drafts,
    caveats,
    policyViolations,
    generatedAt: now.toISOString(),
  };
}

function buildActionItems(findings: Finding[], drafts: ChangeDraft[], access: AccessMode): ActionItem[] {
  const items: Omit<ActionItem, 'id'>[] = [];
  const draftFor = (finding: Finding) =>
    drafts.find((draft) => draft.target === finding.id || draft.summary.includes(finding.title));
  const coveredDrafts = new Set<string>();

  for (const finding of findings) {
    if (finding.status === 'fail') {
      const draft = access === 'draft_only' ? draftFor(finding) : undefined;
      if (draft) coveredDrafts.add(draft.id);
      const kind = draft ? 'draft_change' : 'recommendation';
      items.push({
        priority: priorityFor(finding.severity, kind),
        kind,
        title: finding.recommendation ?? `Fix: ${finding.title}`,
        rationale: finding.diagnosis ?? finding.observation,
        findingIds: [finding.id],
        ...(draft ? { draftId: draft.id } : {}),
        requiresHumanApproval: true,
      });
    } else if (finding.status === 'unknown') {
      items.push({
        priority: priorityFor(finding.severity, 'collect_data'),
        kind: 'collect_data',
        title: `Supply the data to judge: ${finding.title}`,
        rationale: finding.downgradeReason ?? 'The skill could not judge this check from the data it had.',
        findingIds: [finding.id],
        requiresHumanApproval: true,
      });
    }
  }
  for (const draft of drafts) {
    if (coveredDrafts.has(draft.id)) continue;
    items.push({
      priority: 2,
      kind: 'draft_change',
      title: draft.summary,
      rationale: draft.rationale,
      findingIds: [],
      draftId: draft.id,
      requiresHumanApproval: true,
    });
  }

  const severityOf = new Map(findings.map((finding) => [finding.id, SEVERITY_RANK[finding.severity]]));
  const rank = (item: Omit<ActionItem, 'id'>) => Math.min(5, ...item.findingIds.map((id) => severityOf.get(id) ?? 5));
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => a.item.priority - b.item.priority || rank(a.item) - rank(b.item) || a.index - b.index)
    .map(({ item }, index) => ({ id: `A${index + 1}`, ...item }));
}

