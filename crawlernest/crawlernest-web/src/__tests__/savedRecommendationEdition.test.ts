/**
 * @jest-environment node
 */
import { savedCaveats, savedEdition } from "@/app/saved-recommendations/page";
import { STANDARD_CAVEATS, editionCaveats } from "@/lib/caveatMessages";

describe("savedEdition", () => {
  it("reads the edition the plan was saved with", () => {
    expect(savedEdition({ rankingYear: 2025 }, {})).toBe(2025);
    expect(savedEdition({ rankingYear: "2025" }, {})).toBe(2025);
  });

  it("falls back to the edition in the stored response metadata", () => {
    expect(savedEdition({}, { metadata: { ranking_year: 2026 } })).toBe(2026);
  });

  it("prefers the request, which is what the page asked for", () => {
    expect(savedEdition({ rankingYear: 2025 }, { metadata: { ranking_year: 2026 } })).toBe(2025);
  });

  it("returns null for a plan saved before the edition was recorded", () => {
    expect(savedEdition({ country: "United States", ielts: 6.5 }, { metadata: {} })).toBeNull();
    expect(savedEdition(undefined, undefined)).toBeNull();
  });

  it("refuses a year the warehouse does not hold, however it was stored", () => {
    // A stale or hand-edited snapshot cannot label itself with an edition that
    // does not exist here; it reads as unrecorded instead.
    for (const value of [1999, 2014, "abc", null, true, 2025.5]) {
      expect(savedEdition({ rankingYear: value }, {})).toBeNull();
    }
  });
});

describe("savedCaveats", () => {
  it("names the snapshot's own edition when it recorded one", () => {
    expect(savedCaveats(2025)).toEqual(editionCaveats(2025));
    expect(savedCaveats(2025)[0]).toContain("2025");
    expect(savedCaveats(2025)[0]).not.toContain("2026");
  });

  it("falls back to the warehouse-wide caveats when the edition is unknown", () => {
    expect(savedCaveats(null)).toEqual(STANDARD_CAVEATS);
    expect(savedCaveats(null)[0]).toContain("2025 and 2026");
  });
});
