/**
 * @jest-environment node
 *
 * CAVEAT_ADMISSION_DATA_STALE is a pair of templates. The frontend's renderer is
 * held to the rule Python (admission_stale_caveat) and Java
 * (AnalyticsService.admissionStaleCaveat) follow, on the same cases, and the
 * templates must appear verbatim in ANALYTICS_EXPLAINABILITY.md.
 */
import { readFileSync } from "fs";
import path from "path";

import {
  ADMISSION_STALE_FETCHED_TEMPLATE,
  ADMISSION_STALE_UNDATED_TEMPLATE,
  CAVEAT_IELTS_MISSING,
  admissionStaleCaveat,
} from "@/lib/caveatMessages";

const EXPLAINABILITY_DOC = path.resolve(__dirname, "../../../../docs/analytics/ANALYTICS_EXPLAINABILITY.md");

describe("admission caveats", () => {
  it("names the oldest fetch date when every fetch was recorded", () => {
    expect(
      admissionStaleCaveat({ fetchDatesRecorded: true, oldestFetchedOn: "2026-03-01", oldestExtractedOn: "2026-08-22" }),
    ).toBe(ADMISSION_STALE_FETCHED_TEMPLATE.replace("{date}", "2026-03-01"));
  });

  it("never passes an extraction date off as a fetch date", () => {
    const caveat = admissionStaleCaveat({
      fetchDatesRecorded: false,
      oldestFetchedOn: "2026-03-01",
      oldestExtractedOn: "2026-08-22",
    });
    expect(caveat).toBe(ADMISSION_STALE_UNDATED_TEMPLATE.replace("{date}", "2026-08-22"));
    expect(caveat).toContain("fetch date was not recorded");
    expect(caveat).not.toContain("fetched on");
  });

  it("claims nothing when there is no admission data", () => {
    expect(admissionStaleCaveat({ fetchDatesRecorded: true, oldestFetchedOn: null, oldestExtractedOn: null })).toBeNull();
  });

  it("is documented verbatim", () => {
    const doc = readFileSync(EXPLAINABILITY_DOC, "utf-8");
    for (const caveat of [CAVEAT_IELTS_MISSING, ADMISSION_STALE_FETCHED_TEMPLATE, ADMISSION_STALE_UNDATED_TEMPLATE]) {
      expect(doc).toContain(caveat);
    }
  });
});
