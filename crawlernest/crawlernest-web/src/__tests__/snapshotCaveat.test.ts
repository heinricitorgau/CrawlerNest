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
  ARCHIVE_EDITION_CAVEAT_TEMPLATE,
  CAVEAT_QS_STALE,
  SNAPSHOT_CAVEAT_TEMPLATE,
  STANDARD_CAVEATS,
  archiveEditionCaveat,
  formatEditionYears,
  snapshotCaveat,
} from "@/lib/caveatMessages";
import {
  DATASET_ARCHIVE_EDITIONS,
  DATASET_YEARS,
  DEFAULT_RANKING_YEAR,
  liveYears,
} from "@/lib/datasetScope";

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

  it("renders today's constant from the editions QS was crawled for", () => {
    // Not from DATASET_YEARS, and since the QS archive release not from every
    // edition QS covers either: the sentence says the data is a snapshot of
    // tables QS published, which is how 2025 and 2026 were obtained. Archive
    // editions say how they were obtained in their own caveat.
    expect(CAVEAT_QS_STALE).toBe(snapshotCaveat(["QS"], liveYears("QS")));
    expect(liveYears("QS")).toEqual([2026, 2025]);
    for (const archived of Object.keys(DATASET_ARCHIVE_EDITIONS.QS)) {
      expect(CAVEAT_QS_STALE).not.toContain(archived);
    }
    expect(STANDARD_CAVEATS[0]).toBe(CAVEAT_QS_STALE);
  });

  it("refuses to name a source over an edition it does not cover", () => {
    // The sentence asserts the named source published those tables. QS holds
    // no 2015, 2017 or 2021.
    expect(() => snapshotCaveat(["QS"], [2017])).toThrow(/2017/);
    expect(() => snapshotCaveat(["QS"], [2021])).toThrow(/2021/);
    expect(() => snapshotCaveat(["QS", "THE"], DATASET_YEARS)).toThrow();
    expect(() => snapshotCaveat(["THE"], [2014])).toThrow(/2014/);
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

  it("renders the QS 2023 archive sentence exactly as Python and Java do", () => {
    // One golden string in all three suites. This renderer once replaced only the first
    // {source}, because String.replace with a string pattern changes one occurrence.
    expect(archiveEditionCaveat("QS", 2023)).toBe(
      "QS 2023 ranks were recovered from an Internet Archive capture of QS's own data file taken on 2026-05-10, not crawled from QS directly, and QS may have revised the table since. QS prints many ranks as bands (for example 201-210); the rank shown here is the lower bound of the printed rank, so it is not comparable position by position with the QS ranks of 2025 and 2026, which are stored as one position per university. A composite or confidence that includes it inherits that imprecision.",
    );
  });

  it("states the archive template verbatim in the explainability doc", () => {
    expect(readFileSync(EXPLAINABILITY_DOC, "utf-8")).toContain(ARCHIVE_EDITION_CAVEAT_TEMPLATE);
  });

  it("refuses to render no editions", () => {
    expect(() => formatEditionYears([])).toThrow();
  });

  it("defaults queries to the newest edition held", () => {
    expect(DEFAULT_RANKING_YEAR).toBe(Math.max(...DATASET_YEARS));
  });
});
