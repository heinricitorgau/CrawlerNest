/**
 * Types shared by the router, the output parser, the safety layer and the engine.
 *
 * Safe-by-design starts here: `AccessMode` has no write value. A task is either
 * read-only analysis or a draft of a change for a person to apply, and nothing in
 * this module can express "apply it to the account".
 */

export type SkillLibrary = 'notfair' | 'claude-ads';

/** Third-party surfaces a skill may read. */
export type Platform =
  | 'google_ads'
  | 'meta_ads'
  | 'youtube_ads'
  | 'linkedin_ads'
  | 'tiktok_ads'
  | 'microsoft_ads'
  | 'search_console'
  | 'ga4'
  | 'website';

/** `read_only` analyses; `draft_only` may also propose changes, which stay drafts. */
export type AccessMode = 'read_only' | 'draft_only';

// ---------------------------------------------------------------------------
// Skill catalog and routing
// ---------------------------------------------------------------------------

export interface SkillDefinition {
  /** `<library>:<skillName>`, e.g. `notfair:seo-analysis`. */
  id: string;
  library: SkillLibrary;
  /** Directory name under the library's `skills/` folder. */
  skillName: string;
  /** The slash command the skill answers to, e.g. `/seo-analysis` or `/ads audit`. */
  command: string;
  /** What the skill is for, in one line. */
  summary: string;
  platforms: readonly Platform[];
  /**
   * Phrases that select the skill. Matched case-insensitively; ASCII phrases on word
   * boundaries, CJK phrases as substrings.
   */
  keywords: readonly string[];
  /** Every group must contribute at least one hit, on top of `keywords`. */
  requireAll?: readonly (readonly string[])[];
  /** Appends the ad platforms named in the input to the command (`/ads audit google`). */
  takesPlatformScope?: boolean;
  /** Dropped when one of these skills is routed too, because it already covers this one. */
  subsumedBy?: readonly string[];
  /** Owns change requests: when the input asks for a change, this skill handles it as a draft. */
  ownsChanges?: boolean;
}

export interface RoutedTask {
  skillId: string;
  library: SkillLibrary;
  skillName: string;
  /** The full command, scope and `--draft` included. Never carries `--apply`. */
  command: string;
  access: AccessMode;
  platforms: Platform[];
  matchedKeywords: string[];
  score: number;
}

export type RouteDecision =
  | {
      status: 'routed';
      input: string;
      /** In the order the user mentioned them. */
      tasks: RoutedTask[];
      wantsChange: boolean;
      notes: string[];
    }
  | {
      status: 'unrouted';
      input: string;
      tasks: [];
      wantsChange: boolean;
      notes: string[];
    };

export interface LoadedSkill {
  definition: SkillDefinition;
  path: string;
  /** Frontmatter `name` and `description`, as written in SKILL.md. */
  name: string;
  description: string;
  /** SKILL.md without its frontmatter. */
  instructions: string;
}

// ---------------------------------------------------------------------------
// The 4-state result
// ---------------------------------------------------------------------------

export type FindingStatus = 'pass' | 'fail' | 'unknown' | 'not_applicable';

export const FINDING_STATUSES: readonly FindingStatus[] = ['pass', 'fail', 'unknown', 'not_applicable'];

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export type Confidence = 'high' | 'medium' | 'low' | 'none';

export interface Evidence {
  /** `E1`, `E2`, … unique within one report. */
  id: string;
  findingId: string;
  /** Where it came from: `google_ads_api`, `ga4_report`, `crawl`, `skill_output`, … */
  source: string;
  detail: string;
  /** A URL, query, export file name or API resource. */
  reference?: string;
  observedAt?: string;
}

export interface Finding {
  id: string;
  title: string;
  status: FindingStatus;
  severity: Severity;
  confidence: Confidence;
  observation: string;
  diagnosis?: string;
  recommendation?: string;
  evidenceIds: string[];
  /** Set when the parser changed the status the skill reported, and why. */
  downgradedFrom?: FindingStatus;
  downgradeReason?: string;
}

export type ActionKind =
  /** Fix something that failed; a recommendation for a person to carry out. */
  | 'recommendation'
  /** Same, but backed by a `ChangeDraft` the user asked for. */
  | 'draft_change'
  /** A check could not be judged: get the data first. */
  | 'collect_data';

export interface ActionItem {
  id: string;
  /** 1 is most urgent. */
  priority: 1 | 2 | 3;
  kind: ActionKind;
  title: string;
  rationale: string;
  findingIds: string[];
  draftId?: string;
  /** Always true: nothing here is carried out by this module. */
  requiresHumanApproval: true;
}

export interface ChangeDraft {
  id: string;
  platform: Platform | 'unspecified';
  /** The campaign, ad group, property or page the change is about. */
  target: string;
  summary: string;
  proposedChange: Readonly<Record<string, unknown>>;
  rationale: string;
  status: 'draft';
  applied: false;
  requiresHumanApproval: true;
  createdAt: string;
}

export type ReportStatus =
  /** Every finding was judged on evidence. */
  | 'complete'
  /** Some checks are unknown or were downgraded; the judged ones stand. */
  | 'provisional'
  /** Nothing could be judged. */
  | 'insufficient_evidence'
  /** The skill did not return a usable result. */
  | 'failed';

export interface IntelligenceReport {
  schemaVersion: '1.0.0';
  skill: { id: string; command: string; library: SkillLibrary };
  access: AccessMode;
  status: ReportStatus;
  summary: Record<FindingStatus, number> & { total: number };
  findings: Finding[];
  evidence: Evidence[];
  /** Ordered by priority, then severity. */
  actionItems: ActionItem[];
  drafts: ChangeDraft[];
  /** What the reader must know about the limits of this result. Never empty. */
  caveats: string[];
  /** Things the skill output did that the read-only policy forbids. */
  policyViolations: string[];
  generatedAt: string;
}

// ---------------------------------------------------------------------------
// Execution
// ---------------------------------------------------------------------------

/** Handed to whatever runs a skill, so the runner cannot plead ignorance of the rules. */
export interface ExecutionPolicy {
  access: AccessMode;
  allowMutations: false;
  /** Operation name prefixes the runner may call on a platform client. */
  allowedOperationPrefixes: readonly string[];
  /** Plain-language rules to put in front of the skill instructions. */
  rules: readonly string[];
}

export interface SkillRunRequest {
  task: RoutedTask;
  skill: LoadedSkill;
  userInput: string;
  policy: ExecutionPolicy;
}

/**
 * Runs one skill and returns its raw result: JSON (Claude Ads findings, or anything
 * with a `findings` array) or a checklist in text. The engine does not care how the
 * runner gets there (a Claude agent loop, a CLI, a fixture), only that it obeys
 * `request.policy`.
 */
export interface SkillRunner {
  run(request: SkillRunRequest): Promise<unknown>;
}

export interface ExecutionPlan {
  decision: RouteDecision;
  steps: Array<{ task: RoutedTask; skill: LoadedSkill; policy: ExecutionPolicy }>;
}

export interface AnalysisResult {
  decision: RouteDecision;
  reports: IntelligenceReport[];
}
