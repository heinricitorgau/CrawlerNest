import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it } from 'node:test';

import {
  DEFAULT_CATALOG,
  MarketingIntelligenceEngine,
  MutationBlockedError,
  SkillNotFoundError,
  SkillRegistry,
  defaultSkillRoots,
  parseFrontmatter,
} from '../src/index.js';
import type { SkillRoots, SkillRunRequest } from '../src/index.js';

/** Skill folders with a SKILL.md for every catalog entry, so the tests do not need the real libraries. */
async function fixtureRoots(): Promise<SkillRoots> {
  const base = await mkdtemp(path.join(tmpdir(), 'mi-skills-'));
  const roots: SkillRoots = { notfair: path.join(base, 'notfair'), 'claude-ads': path.join(base, 'claude-ads') };
  for (const skill of DEFAULT_CATALOG) {
    const dir = path.join(roots[skill.library], skill.skillName);
    await mkdir(dir, { recursive: true });
    await writeFile(
      path.join(dir, 'SKILL.md'),
      `---\nname: ${skill.skillName}\ndescription: >\n  Fixture for\n  ${skill.skillName}.\n---\n\n# ${skill.skillName}\n\nDo the thing.\n`,
    );
  }
  return roots;
}

const NOW = () => new Date('2026-10-21T00:00:00Z');

describe('parseFrontmatter', () => {
  it('reads plain, quoted and folded values', () => {
    const { fields, body } = parseFrontmatter('---\nname: ads\ndescription: "Quoted"\nhint: >\n  folded\n  text\n---\nBody');
    assert.deepEqual(fields, { name: 'ads', description: 'Quoted', hint: 'folded text' });
    assert.equal(body, 'Body');
  });
});

describe('MarketingIntelligenceEngine', () => {
  it('plans each routed task with its SKILL.md and a read-only policy', async () => {
    const engine = new MarketingIntelligenceEngine({ skillRoots: await fixtureRoots(), now: NOW });
    const plan = await engine.plan('分析競爭對手的 SEO 與 GA4 流量變化');
    assert.deepEqual(plan.steps.map((step) => step.skill.name), ['seo-analysis', 'google-analytics']);
    assert.equal(plan.steps[0].skill.description, 'Fixture for seo-analysis.');
    assert.match(plan.steps[0].skill.instructions, /^# seo-analysis/);
    assert.ok(plan.steps.every((step) => step.policy.allowMutations === false && step.policy.access === 'read_only'));
  });

  it('runs each step through the runner and returns one 4-state report per skill', async () => {
    const seen: SkillRunRequest[] = [];
    const engine = new MarketingIntelligenceEngine({
      skillRoots: await fixtureRoots(),
      now: NOW,
      runner: {
        async run(request) {
          seen.push(request);
          return {
            findings: [
              { id: 'X1', title: 'Conversion tracking', status: 'fail', severity: 'critical', evidence: ['0 primary conversions'] },
              { id: 'X2', title: 'Auto-tagging', status: 'pass', evidence: ['gclid present on 100% of clicks'] },
            ],
          };
        },
      },
    });

    const result = await engine.analyze('審計 Google Ads 廣告帳戶表現');
    assert.equal(seen.length, 1);
    assert.equal(seen[0].task.command, '/ads audit google');
    assert.equal(seen[0].userInput, '審計 Google Ads 廣告帳戶表現');
    assert.equal(result.reports.length, 1);
    const [report] = result.reports;
    assert.equal(report.skill.command, '/ads audit google');
    assert.equal(report.status, 'complete');
    assert.deepEqual(report.summary, { pass: 1, fail: 1, unknown: 0, not_applicable: 0, total: 2 });
    assert.equal(report.actionItems[0].priority, 1);
    assert.equal(report.generatedAt, '2026-10-21T00:00:00.000Z');
  });

  it('turns a runner that tried to write into a failed report with the violation recorded', async () => {
    const engine = new MarketingIntelligenceEngine({
      skillRoots: await fixtureRoots(),
      now: NOW,
      runner: {
        async run() {
          throw new MutationBlockedError('google_ads', 'mutateCampaigns');
        },
      },
    });
    const { reports } = await engine.analyze('audit google ads');
    assert.equal(reports[0].status, 'failed');
    assert.match(reports[0].policyViolations[0], /mutateCampaigns/);
  });

  it('refuses to analyze without a runner', async () => {
    const engine = new MarketingIntelligenceEngine({ skillRoots: await fixtureRoots() });
    await assert.rejects(engine.analyze('audit google ads'), /needs a runner/);
  });

  it('fails loudly when a SKILL.md is missing or names a different skill', async () => {
    const roots = await fixtureRoots();
    const registry = new SkillRegistry(roots);
    const seo = DEFAULT_CATALOG.find((skill) => skill.skillName === 'seo-analysis')!;
    await writeFile(registry.pathFor(seo), '---\nname: something-else\n---\n');
    await assert.rejects(registry.load(seo), SkillNotFoundError);

    const empty = new SkillRegistry({ notfair: '/nonexistent', 'claude-ads': '/nonexistent' });
    await assert.rejects(empty.load(seo), /ENOENT/);
  });
});

// The libraries are vendored at the repository root on the machines that have them.
// Where they are, every catalog entry must name a real skill.
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const realRoots = defaultSkillRoots(REPO_ROOT);
const haveLibraries = existsSync(realRoots.notfair) && existsSync(realRoots['claude-ads']);

describe('the catalog against the vendored skill libraries', { skip: haveLibraries ? false : 'notfair-plugin/ or claude-ads/ is not checked out' }, () => {
  it('names a SKILL.md that exists for every entry', async () => {
    const registry = new SkillRegistry(realRoots);
    for (const skill of DEFAULT_CATALOG) {
      const loaded = await registry.load(skill);
      assert.equal(loaded.name, skill.skillName);
    }
  });
});
