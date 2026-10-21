import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { parseAriaSnapshot, parseSnapshot } from '../src/index.js';
import type { SnapshotResponse } from '../src/index.js';

// Shaped like camofox-browser output: Playwright aria YAML with refs after the name.
const SNAPSHOT = [
  '- banner:',
  '  - link "Home" [e1]:',
  '    - /url: https://www.topuniversities.com/',
  '  - searchbox "Search universities" [e2]: National Taiwan',
  '- main:',
  '  - heading "QS World University Rankings 2026" [level=1]',
  '  - paragraph: The 2026 edition ranks 1,500 institutions.',
  '  - checkbox "Show only Asia" [checked] [e3]',
  '  - table "Top universities":',
  '    - rowgroup:',
  '      - row "Rank University":',
  '        - columnheader "Rank"',
  '        - columnheader "University"',
  '    - rowgroup:',
  '      - row "1 MIT":',
  '        - cell "1"',
  '        - cell "Massachusetts Institute of Technology"',
  '      - row "2 Imperial":',
  '        - cell "2"',
  '        - cell:',
  '          - link "Imperial College London" [e4]:',
  '            - /url: /universities/imperial',
  '  - heading "Methodology" [level=2]',
  '  - text: "Scores: weighted"',
  `  - 'link "Rank: 1 \\"MIT\\"" [e5]'`,
  '[... truncated at char 74800 of 120000. Call snapshot with offset=74800 to see more. Pagination links below. ...]',
  '- navigation "pagination":',
  '  - link "Next" [e6]',
].join('\n');

const RESPONSE: SnapshotResponse = {
  url: 'https://www.topuniversities.com/world-university-rankings',
  snapshot: SNAPSHOT,
  refsCount: 6,
  truncated: true,
  totalChars: 120000,
  hasMore: true,
  nextOffset: 74800,
};

describe('parseSnapshot', () => {
  const page = parseSnapshot(RESPONSE, { capturedAt: new Date('2026-10-21T00:00:00Z') });

  it('reads every line', () => {
    assert.deepEqual(page.warnings, []);
  });

  it('collects headings and the primary heading', () => {
    assert.equal(page.primaryHeading, 'QS World University Rankings 2026');
    assert.deepEqual(page.headings, [
      { level: 1, text: 'QS World University Rankings 2026' },
      { level: 2, text: 'Methodology' },
    ]);
  });

  it('collects links with their href and ref', () => {
    assert.deepEqual(page.links[0], { text: 'Home', href: 'https://www.topuniversities.com/', ref: 'e1' });
    assert.deepEqual(page.links.find((l) => l.ref === 'e4'), { text: 'Imperial College London', href: '/universities/imperial', ref: 'e4' });
    assert.equal(page.links.find((l) => l.ref === 'e6')?.text, 'Next');
  });

  it('lists interactive elements with values and states', () => {
    assert.deepEqual(page.interactive.map((e) => e.ref), ['e1', 'e2', 'e3', 'e4', 'e5', 'e6']);
    assert.equal(page.interactive[1].value, 'National Taiwan');
    assert.deepEqual(page.interactive[2].states, { checked: true });
  });

  it('unquotes YAML-quoted keys and values', () => {
    assert.equal(page.interactive[4].name, 'Rank: 1 "MIT"');
    assert.ok(page.textBlocks.includes('Scores: weighted'));
  });

  it('builds tables from the aria tree when there is no DOM summary', () => {
    assert.equal(page.tables.length, 1);
    assert.deepEqual(page.tables[0], {
      origin: 'aria',
      label: 'Top universities',
      headers: ['Rank', 'University'],
      rows: [['1', 'Massachusetts Institute of Technology'], ['2', 'Imperial College London']],
      rowsTruncated: true,
    });
  });

  it('keeps table text out of textBlocks', () => {
    assert.deepEqual(page.textBlocks, ['The 2026 edition ranks 1,500 institutions.', 'Scores: weighted']);
  });

  it('reports truncation', () => {
    assert.deepEqual(page.completeness, { truncated: true, totalChars: 120000, hasMore: true, nextOffset: 74800 });
  });

  it('prefers the DOM table summary when the server sends one', () => {
    const withStructure = parseSnapshot({
      ...RESPONSE,
      structure: {
        forms: [],
        formsTruncated: false,
        tables: [{ label: 'Rankings', headers: ['Rank'], columns: ['Rank'], rowCount: 1500, rows: [['1']], rowsTruncated: true }],
        tablesTruncated: false,
      },
    });
    assert.deepEqual(withStructure.tables, [{ origin: 'dom', label: 'Rankings', headers: ['Rank'], rows: [['1']], rowsTruncated: true }]);
  });
});

describe('parseAriaSnapshot', () => {
  it('turns unreadable lines into warnings instead of throwing', () => {
    const { tree, warnings } = parseAriaSnapshot('ion" [e3]\n- heading "ok"\n- link "unterminated');
    assert.equal(tree.length, 1);
    assert.equal(warnings.length, 2);
  });
});
