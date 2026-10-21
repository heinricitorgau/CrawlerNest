import { AD_PLATFORM_TERMS, CHANGE_TERMS, COMPETITOR_TERMS, DEFAULT_CATALOG } from './catalog.js';
import type { AccessMode, Platform, RouteDecision, RoutedTask, SkillDefinition } from './types.js';

interface Hit {
  term: string;
  position: number;
}

const ASCII_ONLY = /^[\x20-\x7e]+$/;

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Lower-cased, width-folded and with runs of whitespace collapsed, so `ＧＡ４` reads as `ga4`. */
export function normalizeInput(input: string): string {
  return input.normalize('NFKC').toLowerCase().replace(/\s+/g, ' ').trim();
}

/**
 * Where `term` first occurs in `text`, or -1. ASCII terms must stand on word
 * boundaries (`ga4` does not match `saga4x`); CJK terms have none, so any substring counts.
 */
function findTerm(text: string, term: string): number {
  const needle = term.toLowerCase();
  if (!ASCII_ONLY.test(needle)) return text.indexOf(needle);
  const match = new RegExp(`(?<![a-z0-9])${escapeRegExp(needle)}(?![a-z0-9])`).exec(text);
  return match ? match.index : -1;
}

function findHits(text: string, terms: readonly string[]): Hit[] {
  const hits: Hit[] = [];
  for (const term of terms) {
    const position = findTerm(text, term);
    if (position >= 0) hits.push({ term, position });
  }
  return hits;
}

/** A multi-word phrase is better evidence of intent than a single word. */
function weight(term: string): number {
  return term.includes(' ') || term.length >= 4 ? 2 : 1;
}

function detectAdPlatforms(text: string): Array<{ platform: Platform; scope: string; position: number }> {
  const found: Array<{ platform: Platform; scope: string; position: number }> = [];
  for (const entry of AD_PLATFORM_TERMS) {
    const positions = findHits(text, entry.terms).map((hit) => hit.position);
    if (positions.length) found.push({ platform: entry.platform, scope: entry.scope, position: Math.min(...positions) });
  }
  return found.sort((a, b) => a.position - b.position);
}

interface Candidate {
  skill: SkillDefinition;
  score: number;
  position: number;
  matchedKeywords: string[];
}

function scoreSkill(text: string, skill: SkillDefinition): Candidate | null {
  const hits = findHits(text, skill.keywords);
  if (!hits.length) return null;
  const groupHits: Hit[] = [];
  for (const group of skill.requireAll ?? []) {
    const found = findHits(text, group);
    if (!found.length) return null;
    groupHits.push(...found);
  }
  const all = [...hits, ...groupHits];
  return {
    skill,
    score: hits.reduce((sum, hit) => sum + weight(hit.term), 0),
    position: Math.min(...all.map((hit) => hit.position)),
    matchedKeywords: [...new Set(all.map((hit) => hit.term))],
  };
}

export interface IntentRouterOptions {
  catalog?: readonly SkillDefinition[];
}

/**
 * Turns a request in plain language into the skills that should answer it.
 *
 * It is deterministic keyword routing, not a model call: the same sentence always
 * goes to the same skills, and `matchedKeywords` says why. A request that names
 * several things ("SEO and GA4") gets one task per skill, in the order mentioned;
 * each task still has exactly one owning skill.
 */
export class IntentRouter {
  private readonly catalog: readonly SkillDefinition[];

  constructor(options: IntentRouterOptions = {}) {
    this.catalog = options.catalog ?? DEFAULT_CATALOG;
  }

  route(input: string): RouteDecision {
    const text = normalizeInput(input);
    const notes: string[] = [];

    const applyRequested = /(^|\s)--apply(\s|$)/.test(text);
    const routedText = text.replace(/(^|\s)--(apply|draft)(?=\s|$)/g, ' ').trim();
    const wantsChange = applyRequested || findHits(routedText, CHANGE_TERMS).length > 0;
    if (applyRequested) {
      notes.push('`--apply` was requested and ignored: this engine never writes to an account; the change is returned as a draft.');
    }

    let candidates = this.catalog
      .map((skill) => scoreSkill(routedText, skill))
      .filter((candidate): candidate is Candidate => candidate !== null);

    const chosen = new Set(candidates.map((candidate) => candidate.skill.id));
    candidates = candidates.filter((candidate) => !(candidate.skill.subsumedBy ?? []).some((id) => chosen.has(id)));

    // A change to an ad account belongs to the skill that owns changes, as a draft.
    if (wantsChange && candidates.some((candidate) => candidate.skill.library === 'claude-ads')) {
      const owner = this.catalog.find((skill) => skill.ownsChanges);
      if (owner && !candidates.some((candidate) => candidate.skill.id === owner.id)) {
        const anchor = Math.min(...candidates.map((candidate) => candidate.position));
        candidates.push({ skill: owner, score: 1, position: anchor + 0.5, matchedKeywords: ['(change request)'] });
      }
    }

    if (!candidates.length) {
      notes.push('No skill matched. Name the platform or the analysis (e.g. "SEO", "GA4", "Google Ads audit").');
      return { status: 'unrouted', input, tasks: [], wantsChange, notes };
    }

    candidates.sort((a, b) => a.position - b.position || b.score - a.score);

    const adPlatforms = detectAdPlatforms(routedText);
    const access: AccessMode = wantsChange ? 'draft_only' : 'read_only';
    const tasks = candidates.map((candidate) => this.toTask(candidate, adPlatforms, access));

    const competitorMentioned = findHits(routedText, COMPETITOR_TERMS).length > 0;
    if (competitorMentioned && tasks.some((task) => task.platforms.some((p) => p === 'ga4' || p === 'search_console'))) {
      notes.push(
        'GA4 and Search Console only expose properties you own: they describe your site, not a competitor. ' +
          'Competitor figures can only come from public sources and are estimates.',
      );
    }
    if (wantsChange) {
      notes.push('A change was asked for: every task runs read-only and returns its proposals as drafts for a person to apply.');
    }

    return { status: 'routed', input, tasks, wantsChange, notes };
  }

  private toTask(
    candidate: Candidate,
    adPlatforms: Array<{ platform: Platform; scope: string }>,
    access: AccessMode,
  ): RoutedTask {
    const { skill } = candidate;
    let command = skill.command;
    let platforms: Platform[] = [...skill.platforms];

    if (skill.library === 'claude-ads' && adPlatforms.length) {
      const named = adPlatforms.filter((entry) => skill.platforms.includes(entry.platform));
      if (named.length) platforms = named.map((entry) => entry.platform);
      if (skill.takesPlatformScope) command += ` ${named.map((entry) => entry.scope).join(' ') || 'all'}`;
    } else if (skill.takesPlatformScope) {
      command += ' all';
    }
    if (skill.ownsChanges) command += ' --draft';

    return {
      skillId: skill.id,
      library: skill.library,
      skillName: skill.skillName,
      command,
      access: skill.ownsChanges ? 'draft_only' : access,
      platforms,
      matchedKeywords: candidate.matchedKeywords,
      score: candidate.score,
    };
  }
}
