import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { MutationBlockedError, createDraft, executionPolicy, guardPlatformClient, isReadOperation } from '../src/index.js';

describe('isReadOperation', () => {
  it('accepts read verbs and denies everything else by default', () => {
    for (const name of ['getCampaign', 'listAccessibleCustomers', 'search', 'searchStream', 'runReport', 'query', 'get_campaign']) {
      assert.equal(isReadOperation(name), true, name);
    }
    for (const name of ['mutate', 'mutateCampaigns', 'update', 'pause', 'create', 'remove', 'getter_then_set', 'gettysburg', 'doSomething']) {
      assert.equal(isReadOperation(name), false, name);
    }
  });
});

describe('guardPlatformClient', () => {
  function fakeAdsClient() {
    const calls: string[] = [];
    const campaign = {
      id: '42',
      pause: () => calls.push('pause'),
    };
    return {
      calls,
      client: {
        customers: {
          search: async (query: string) => {
            calls.push(`search ${query}`);
            return [campaign];
          },
          mutate: () => calls.push('mutate'),
        },
        getCampaign: () => campaign,
      },
    };
  }

  it('lets reads through', async () => {
    const { client, calls } = fakeAdsClient();
    const guarded = guardPlatformClient('google_ads', client);
    const rows = await guarded.customers.search('SELECT campaign.id FROM campaign');
    assert.equal(rows.map((row) => row.id).join(), '42');
    assert.deepEqual(calls, ['search SELECT campaign.id FROM campaign']);
  });

  it('blocks a write at any depth before it runs', () => {
    const { client, calls } = fakeAdsClient();
    const guarded = guardPlatformClient('google_ads', client);
    assert.throws(() => guarded.customers.mutate(), MutationBlockedError);
    assert.deepEqual(calls, []);
  });

  it('blocks a write on an object a read returned, sync or async', async () => {
    const { client, calls } = fakeAdsClient();
    const guarded = guardPlatformClient('google_ads', client);
    assert.throws(() => guarded.getCampaign().pause(), MutationBlockedError);
    const [row] = await guarded.customers.search('q');
    assert.throws(() => row.pause(), (error: unknown) => error instanceof MutationBlockedError && error.operation === 'pause');
    assert.ok(!calls.includes('pause'));
  });
});

describe('createDraft', () => {
  it('makes a frozen draft that cannot be marked applied', () => {
    const draft = createDraft({ platform: 'meta_ads', target: 'adset/7', summary: 'Cap frequency at 3', proposedChange: { frequency_cap: 3 } });
    assert.equal(draft.status, 'draft');
    assert.equal(draft.applied, false);
    assert.equal(draft.requiresHumanApproval, true);
    assert.throws(() => {
      (draft as { applied: boolean }).applied = true;
    }, TypeError);
    assert.throws(() => {
      (draft.proposedChange as Record<string, unknown>).frequency_cap = 10;
    }, TypeError);
  });
});

describe('executionPolicy', () => {
  it('never allows mutations, and asks for drafts only when changes were requested', () => {
    const read = executionPolicy('read_only');
    const draft = executionPolicy('draft_only');
    assert.equal(read.allowMutations, false);
    assert.equal(draft.allowMutations, false);
    assert.ok(draft.rules.some((rule) => rule.includes('proposed_changes')));
    assert.ok(!read.rules.some((rule) => rule.includes('"proposed_changes" as')));
  });
});
