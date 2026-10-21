import { DEFAULT_CATALOG } from './catalog.js';
import { IntentRouter } from './intentRouter.js';
import { BASE_CAVEATS, parseSkillOutput } from './outputParser.js';
import { executionPolicy } from './safety.js';
import { SkillRegistry } from './skillRegistry.js';
import type { SkillRoots } from './skillRegistry.js';
import type {
  AnalysisResult,
  ExecutionPlan,
  IntelligenceReport,
  RouteDecision,
  RoutedTask,
  SkillDefinition,
  SkillRunner,
} from './types.js';

export interface MarketingIntelligenceEngineOptions {
  skillRoots: SkillRoots;
  catalog?: readonly SkillDefinition[];
  /** Needed only for `analyze`; `route`, `plan` and `parse` work without one. */
  runner?: SkillRunner;
  now?: () => Date;
}

/**
 * Request in, structured findings out:
 *
 *   route(input)   → which skills, in what mode (read-only or draft-only)
 *   plan(input)    → plus each SKILL.md and the execution policy for the runner
 *   analyze(input) → runs each step through the injected `SkillRunner` and parses
 *                    the result into a 4-state `IntelligenceReport`
 *
 * The engine holds no platform credentials and makes no platform calls. A runner
 * that does should wrap its clients with `guardPlatformClient`.
 */
export class MarketingIntelligenceEngine {
  private readonly router: IntentRouter;
  private readonly registry: SkillRegistry;
  private readonly catalog: readonly SkillDefinition[];
  private readonly runner?: SkillRunner;
  private readonly now: () => Date;

  constructor(options: MarketingIntelligenceEngineOptions) {
    this.catalog = options.catalog ?? DEFAULT_CATALOG;
    this.router = new IntentRouter({ catalog: this.catalog });
    this.registry = new SkillRegistry(options.skillRoots);
    this.runner = options.runner;
    this.now = options.now ?? (() => new Date());
  }

  route(input: string): RouteDecision {
    return this.router.route(input);
  }

  async plan(input: string): Promise<ExecutionPlan> {
    const decision = this.route(input);
    const steps = await Promise.all(
      decision.tasks.map(async (task) => ({
        task,
        skill: await this.registry.load(this.definitionOf(task)),
        policy: executionPolicy(task.access),
      })),
    );
    return { decision, steps };
  }

  parse(task: RoutedTask, rawOutput: unknown): IntelligenceReport {
    return parseSkillOutput(rawOutput, { task, now: this.now() });
  }

  async analyze(input: string): Promise<AnalysisResult> {
    if (!this.runner) throw new Error('MarketingIntelligenceEngine.analyze needs a runner; pass one in the options.');
    const { decision, steps } = await this.plan(input);
    const reports: IntelligenceReport[] = [];
    // One at a time: tasks may share rate-limited platform APIs.
    for (const step of steps) {
      try {
        const raw = await this.runner.run({ ...step, userInput: input });
        reports.push(this.parse(step.task, raw));
      } catch (error) {
        reports.push(this.failedReport(step.task, error));
      }
    }
    return { decision, reports };
  }

  private definitionOf(task: RoutedTask): SkillDefinition {
    const definition = this.catalog.find((skill) => skill.id === task.skillId);
    if (!definition) throw new Error(`Routed to ${task.skillId}, which is not in the catalog.`);
    return definition;
  }

  private failedReport(task: RoutedTask, error: unknown): IntelligenceReport {
    const message = error instanceof Error ? error.message : String(error);
    return {
      schemaVersion: '1.0.0',
      skill: { id: task.skillId, command: task.command, library: task.library },
      access: task.access,
      status: 'failed',
      summary: { pass: 0, fail: 0, unknown: 0, not_applicable: 0, total: 0 },
      findings: [],
      evidence: [],
      actionItems: [],
      drafts: [],
      caveats: [...BASE_CAVEATS, `The skill run failed and nothing was judged: ${message}`],
      policyViolations: error instanceof Error && error.name === 'MutationBlockedError' ? [message] : [],
      generatedAt: this.now().toISOString(),
    };
  }
}
