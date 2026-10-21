import assert from 'node:assert/strict';
import { beforeEach, describe, it } from 'node:test';

import { normalizeStatus, parseSkillOutput, resetDraftIds } from '../src/index.js';
import type { RoutedTask } from '../src/index.js';

const NOW = new Date('2026-10-21T00:00:00Z');

function task(overrides: Partial<RoutedTask> = {}): RoutedTask {
  return {
    skillId: 'claude-ads:ads-audit',
    library: 'claude-ads',
    skillName: 'ads-audit',
    command: '/ads audit google',
    access: 'read_only',
    platforms: ['google_ads'],
    matchedKeywords: ['audit'],
    score: 2,
    ...overrides,
  };
}

/** A Claude Ads AuditWorkerResult, as its `models.py` defines it. */
const WORKER_RESULT = {
  schema_version: '1.0.0',
  status: 'ok',
  platform: 'google',
  scope: ['conversion_tracking', 'search_terms'],
  findings: [
    {
      control_id: 'G-CT-01',
      status: 'fail',
      severity: 'critical',
      confidence: 'high',
      observation: 'No primary conversion action is enabled',
      diagnosis: 'Smart bidding has nothing to optimise for',
      recommendation: 'Mark the lead form submit as the primary conversion',
      evidence: [{ source: 'google_ads_api', detail: 'conversion_action: 0 rows with primary_for_goal=true', reference: 'customers/123/conversionActions' }],
    },
    {
      control_id: 'G-ST-02',
      status: 'pass',
      severity: 'medium',
      observation: 'Negative keyword lists are attached to all search campaigns',
      evidence: [{ source: 'google_ads_api', detail: '4 of 4 campaigns have a shared negative list' }],
    },
    { control_id: 'G-PMAX-01', status: 'not_applicable', severity: 'medium', observation: 'No Performance Max campaigns' },
    { control_id: 'G-BID-03', status: 'pass', severity: 'high', observation: 'Bidding looks fine' },
    { control_id: 'G-LP-01', status: 'unknown', severity: 'high', observation: 'Landing page speed not measured' },
  ],
  missing_inputs: ['PageSpeed report'],
};

describe('normalizeStatus', () => {
  it('maps synonyms in English, Chinese and emoji onto the four states', () => {
    const cases: Array<[unknown, string]> = [
      ['PASS', 'pass'], ['✅', 'pass'], ['通過', 'pass'],
      ['Warning', 'fail'], ['needs-improvement', 'fail'], ['需優化', 'fail'], ['❌', 'fail'],
      ['missing', 'unknown'], ['數據缺失', 'unknown'], [undefined, 'unknown'],
      ['N/A', 'not_applicable'], ['not applicable', 'not_applicable'], ['不適用', 'not_applicable'],
    ];
    for (const [raw, expected] of cases) assert.equal(normalizeStatus(raw).status, expected, String(raw));
  });

  it('treats an unrecognised status as unknown, never as pass', () => {
    assert.deepEqual(normalizeStatus('looks great'), { status: 'unknown', recognised: false });
  });
});

describe('parseSkillOutput', () => {
  beforeEach(() => resetDraftIds());

  it('parses a Claude Ads worker result into findings, evidence and ranked action items', () => {
    const report = parseSkillOutput(WORKER_RESULT, { task: task(), now: NOW });

    assert.equal(report.schemaVersion, '1.0.0');
    assert.deepEqual(report.summary, { pass: 1, fail: 1, unknown: 2, not_applicable: 1, total: 5 });
    assert.equal(report.status, 'provisional');

    const ct = report.findings.find((f) => f.id === 'G-CT-01');
    assert.ok(ct);
    assert.equal(ct.status, 'fail');
    assert.equal(ct.confidence, 'high');
    assert.deepEqual(ct.evidenceIds, ['E1']);
    assert.equal(report.evidence[0].reference, 'customers/123/conversionActions');

    // The critical failure comes first; missing data follows, below it.
    assert.equal(report.actionItems[0].findingIds[0], 'G-CT-01');
    assert.equal(report.actionItems[0].priority, 1);
    assert.equal(report.actionItems[0].kind, 'recommendation');
    assert.ok(report.actionItems.slice(1).every((item) => item.kind === 'collect_data' && item.priority === 2));
    assert.ok(report.actionItems.every((item) => item.requiresHumanApproval === true));
    assert.ok(report.caveats.some((c) => c.includes('missing inputs: PageSpeed report')));
  });

  it('downgrades a pass with no evidence to unknown and says why', () => {
    const report = parseSkillOutput(WORKER_RESULT, { task: task(), now: NOW });
    const bid = report.findings.find((f) => f.id === 'G-BID-03');
    assert.ok(bid);
    assert.equal(bid.status, 'unknown');
    assert.equal(bid.downgradedFrom, 'pass');
    assert.equal(bid.confidence, 'none');
    assert.ok(report.caveats.some((c) => c.includes('without evidence')));
  });

  it('reads JSON inside a fenced block in a text answer', () => {
    const text = 'Here is the audit:\n```json\n{"findings":[{"id":"S1","title":"Sitemap submitted","status":"PASS","evidence":["GSC sitemaps: 1 submitted, 0 errors"]}]}\n```\nDone.';
    const report = parseSkillOutput(text, { task: task({ skillId: 'notfair:seo-analysis', library: 'notfair' }), now: NOW });
    assert.equal(report.status, 'complete');
    assert.equal(report.findings[0].status, 'pass');
    assert.equal(report.evidence[0].detail, 'GSC sitemaps: 1 submitted, 0 errors');
  });

  it('parses a text checklist, keeping only the lines that carry a status', () => {
    const text = [
      '# SEO checklist',
      '- [PASS] SEO-1: HTTPS everywhere — evidence: 0 http URLs in crawl',
      '- ❌ Title tags too long | 37 of 120 pages over 60 characters',
      '- [N/A] Hreflang',
      '- [x] a task box, not a status',
      '- ⚠️ Core Web Vitals',
    ].join('\n');
    const report = parseSkillOutput(text, { task: task(), now: NOW });
    assert.deepEqual(report.findings.map((f) => [f.id, f.status]), [
      ['SEO-1', 'pass'], ['F2', 'fail'], ['F3', 'not_applicable'], ['F4', 'unknown'],
    ]);
    assert.equal(report.findings[3].downgradedFrom, 'fail');
    assert.equal(report.evidence[0].source, 'skill_output');
  });

  it('keeps proposed changes as frozen drafts and links them to the failure they fix', () => {
    const output = {
      findings: [{ id: 'G-CT-01', title: 'Primary conversion', status: 'fail', severity: 'high', evidence: ['0 primary conversions'] }],
      proposed_changes: [
        { platform: 'google', target: 'G-CT-01', summary: 'Set form submit as primary', change: { primary_for_goal: true } },
        { platform: 'google', target: 'campaign/42', summary: 'Lower the tCPA by 10%', rationale: 'CPA is 30% under target' },
      ],
    };
    const report = parseSkillOutput(output, { task: task({ access: 'draft_only' }), now: NOW });

    assert.equal(report.drafts.length, 2);
    for (const draft of report.drafts) {
      assert.equal(draft.status, 'draft');
      assert.equal(draft.applied, false);
      assert.equal(draft.platform, 'google_ads');
      assert.ok(Object.isFrozen(draft));
    }
    assert.equal(report.actionItems[0].kind, 'draft_change');
    assert.equal(report.actionItems[0].draftId, report.drafts[0].id);
    assert.equal(report.actionItems[1].draftId, report.drafts[1].id);
    assert.deepEqual(report.policyViolations, []);
  });

  it('records a claim that a change was applied as a policy violation', () => {
    const output = {
      findings: [{ id: 'A', status: 'fail', evidence: ['x'] }],
      proposed_changes: [{ summary: 'Paused 3 ad groups', status: 'applied' }],
    };
    const report = parseSkillOutput(output, { task: task({ access: 'draft_only' }), now: NOW });
    assert.equal(report.drafts[0].applied, false);
    assert.equal(report.policyViolations.length, 1);
    assert.match(report.policyViolations[0], /Paused 3 ad groups/);
  });

  it('flags changes proposed in a read-only task', () => {
    const report = parseSkillOutput(
      { findings: [{ id: 'A', status: 'pass', evidence: ['x'] }], proposed_changes: [{ summary: 'Raise budget' }] },
      { task: task(), now: NOW },
    );
    assert.ok(report.policyViolations.some((v) => v.includes('read-only task')));
  });

  it('reports failure, not an empty pass, when nothing can be read', () => {
    const report = parseSkillOutput('I could not access the account.', { task: task(), now: NOW });
    assert.equal(report.status, 'failed');
    assert.equal(report.summary.total, 0);
    assert.ok(report.caveats.length > 2);
  });

  it('calls a report with only unknown and not-applicable checks insufficient evidence', () => {
    const report = parseSkillOutput({ findings: [{ id: 'A', status: 'unknown' }, { id: 'B', status: 'n/a' }] }, { task: task(), now: NOW });
    assert.equal(report.status, 'insufficient_evidence');
  });
});
