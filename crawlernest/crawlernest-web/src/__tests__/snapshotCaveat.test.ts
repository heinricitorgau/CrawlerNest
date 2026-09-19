/**
 * @jest-environment node
 *
 * The snapshot caveat is rendered from a template, so the frontend's renderer is
 * held to the same two things Python and Java are: the sentence it produces for
 * the 2026-only warehouse is exactly the one the constant used to hold, and a
 * list of years joins as ANALYTICS_EXPLAINABILITY.md specifies.
 */
import { readFileSync } from "fs";
import path from "path";

import {
  CAVEAT_QS_STALE,
  SNAPSHOT_CAVEAT_TEMPLATE,
  STANDARD_CAVEATS,
  formatEditionYears,
  snapshotCaveat,
} from "@/lib/caveatMessages";
import { DATASET_COVERAGE, DATASET_YEARS, DEFAULT_RANKING_YEAR } from "@/lib/datasetScope";

const SNAPSHOT_CAVEAT_2026 =
  "QS ranking data is a point-in-time snapshot of the 2026 published tables. Figures may not reflect rankings republished since this snapshot was ingested.";

const EXPLAINABILITY_DOC = path.resolve(
  __dirname,
  "../../../../docs/analytics/ANALYTICS_EXPLAINABILITY.md",
);

function documentedRenderings(doc: string): Array<[number[], string]> {
  const block = doc
    .split("<!-- year-list-rendering:start -->")[1]
    .split("<!-- year-list-rendering:end -->")[0];
  return block
    .trim()
    .split(/\r?\n/)
    .map((line) => line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim()))
    .filter((cells) => cells.length === 2 && /^\d/.test(cells[0]))
    .map(([editions, rendered]) => [editions.split(",").map((y) => Number(y.trim())), rendered]);
}

describe("snapshot caveat template", () => {
  it("renders the 2026 sentence the constant used to hold", () => {
    expect(snapshotCaveat(["QS"], [2026])).toBe(SNAPSHOT_CAVEAT_2026);
  });

  it("renders today's constant from the editions QS covers", () => {
    // Not from DATASET_YEARS. The two were the same list until the 2015-2024
    // ARWU release; rendering from the union would name ten editions in which
    // QS published nothing here.
    expect(CAVEAT_QS_STALE).toBe(snapshotCaveat(["QS"], DATASET_COVERAGE.QS));
    expect(STANDARD_CAVEATS[0]).toBe(CAVEAT_QS_STALE);
  });

  it("refuses to name a source over an edition it does not cover", () => {
    // The sentence asserts the named source published those tables. For the
    // ARWU-only editions, QS did not.
    expect(() => snapshotCaveat(["QS"], [2018])).toThrow(/2018/);
    expect(() => snapshotCaveat(["QS", "THE"], DATASET_YEARS)).toThrow();
    expect(snapshotCaveat(["ARWU"], [2018])).toContain("ARWU ranking data");
  });

  it("joins year lists as the explainability doc specifies", () => {
    const doc = readFileSync(EXPLAINABILITY_DOC, "utf-8");
    expect(doc).toContain(SNAPSHOT_CAVEAT_TEMPLATE);

    const rows = documentedRenderings(doc);
    expect(rows.length).toBeGreaterThanOrEqual(3);
    for (const [editions, rendered] of rows) {
      expect(formatEditionYears(editions)).toBe(rendered);
    }
  });

  it("refuses to render no editions", () => {
    expect(() => formatEditionYears([])).toThrow();
  });

  it("defaults queries to the newest edition held", () => {
    expect(DEFAULT_RANKING_YEAR).toBe(Math.max(...DATASET_YEARS));
  });
});
