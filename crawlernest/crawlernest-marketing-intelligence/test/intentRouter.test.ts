import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { IntentRouter } from '../src/index.js';

const router = new IntentRouter();

function commands(input: string): string[] {
  return router.route(input).tasks.map((task) => task.command);
}

describe('IntentRouter', () => {
  it('sends a competitor SEO and GA4 question to the two NotFair skills, in the order asked', () => {
    const decision = router.route('分析競爭對手的 SEO 與 GA4 流量變化');
    assert.equal(decision.status, 'routed');
    assert.deepEqual(decision.tasks.map((task) => task.command), ['/seo-analysis', '/google-analytics']);
    assert.ok(decision.tasks.every((task) => task.access === 'read_only'));
    assert.equal(decision.wantsChange, false);
    // A competitor's GA4 is not something anyone can read; the decision says so.
    assert.ok(decision.notes.some((note) => note.includes('only expose properties you own')));
  });

  it('does not send a competitor mention to the ads competitor skill without an ad term', () => {
    assert.ok(!commands('分析競爭對手的 SEO').includes('/ads competitor'));
  });

  it('sends a Google Ads account audit to Claude Ads with the platform as scope', () => {
    const decision = router.route('審計 Google Ads 廣告帳戶表現');
    assert.deepEqual(decision.tasks.map((task) => task.command), ['/ads audit google']);
    assert.deepEqual(decision.tasks[0].platforms, ['google_ads']);
    assert.equal(decision.tasks[0].access, 'read_only');
  });

  it('scopes an audit to every ad platform named, and to all when none is', () => {
    assert.deepEqual(commands('Audit our Meta Ads and Google Ads campaigns'), ['/ads audit meta google']);
    assert.deepEqual(commands('audit our paid ads'), ['/ads audit all']);
  });

  it('turns a change request into a draft owned by ads-optimize', () => {
    const decision = router.route('審計 Google Ads 表現，然後暫停表現差的廣告');
    assert.equal(decision.wantsChange, true);
    const optimize = decision.tasks.find((task) => task.skillName === 'ads-optimize');
    assert.ok(optimize);
    assert.equal(optimize.command, '/ads optimize --draft');
    assert.ok(decision.tasks.every((task) => task.access === 'draft_only'));
  });

  it('never passes --apply through, and says it ignored it', () => {
    const decision = router.route('/ads optimize google ads campaign bids --apply');
    assert.ok(decision.tasks.every((task) => !task.command.includes('--apply')));
    assert.ok(decision.tasks.every((task) => task.access === 'draft_only'));
    assert.ok(decision.notes.some((note) => note.includes('--apply')));
  });

  it('lets SEO analysis absorb a Search Console mention instead of running both', () => {
    assert.deepEqual(commands('SEO audit using Search Console data'), ['/seo-analysis']);
    assert.deepEqual(commands('check my search console CTR'), ['/search-console']);
  });

  it('matches ASCII terms on word boundaries and folds full-width text', () => {
    assert.deepEqual(commands('ＧＡ４ 跳出率'), ['/google-analytics']);
    assert.equal(router.route('the saga4x report').status, 'unrouted');
  });

  it('reports an unrouted request instead of guessing', () => {
    const decision = router.route('幫我寫一首詩');
    assert.equal(decision.status, 'unrouted');
    assert.deepEqual(decision.tasks, []);
    assert.ok(decision.notes.length > 0);
  });
});
