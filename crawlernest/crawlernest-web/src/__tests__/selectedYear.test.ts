/**
 * @jest-environment node
 */
import { SNAPSHOT_CAVEAT_TEMPLATE, CAVEAT_ARWU_PARTIAL, CAVEAT_THE_PARTIAL, STANDARD_CAVEATS, editionCaveats } from "@/lib/caveatMessages";
import { DATASET_YEARS, DEFAULT_RANKING_YEAR, hrefWithYear, resolveSelectedYear } from "@/lib/datasetScope";
import { isYearAwarePath } from "@/components/NavBar";

jest.mock("@/hooks/useAuthPlaceholder", () => ({ useAuth: () => ({}) }));

describe("resolveSelectedYear", () => {
  it("reads the default edition when the URL names none", () => {
    for (const raw of [null, undefined, "", "  "]) {
      expect(resolveSelectedYear(raw)).toEqual({ year: DEFAULT_RANKING_YEAR, requested: null, requestedHeld: true });
    }
  });

  it("reads every held edition", () => {
    for (const year of DATASET_YEARS) {
      expect(resolveSelectedYear(String(year))).toEqual({ year, requested: String(year), requestedHeld: true });
    }
  });

  it("never queries an edition that is not held, and says it was asked for", () => {
    for (const raw of ["2019", "2027", "20250", "2025abc", "abc", "-2025"]) {
      expect(resolveSelectedYear(raw)).toEqual({ year: DEFAULT_RANKING_YEAR, requested: raw, requestedHeld: false });
    }
  });
});

describe("hrefWithYear", () => {
  it("adds the edition and keeps any query already there", () => {
    expect(hrefWithYear("/", 2025)).toBe("/?year=2025");
    expect(hrefWithYear("/compare?ids=1,2", 2025)).toBe("/compare?ids=1%2C2&year=2025");
    expect(hrefWithYear("/?year=2026", 2025)).toBe("/?year=2025");
  });
});

describe("isYearAwarePath", () => {
  it("covers the pages whose data depends on the edition and no others", () => {
    for (const path of ["/", "/rankings", "/recommendations", "/compare"]) expect(isYearAwarePath(path)).toBe(true);
    for (const path of ["/about", "/analytics", "/universities/mit", "/rankings/extra"]) expect(isYearAwarePath(path)).toBe(false);
  });
});

describe("editionCaveats", () => {
  it("names only the edition a page shows, from the shared template", () => {
    const shown = editionCaveats(2025);
    expect(shown[0]).toBe(SNAPSHOT_CAVEAT_TEMPLATE.replace("{years}", "2025"));
    expect(shown[0]).not.toContain("2026");
    expect(editionCaveats(2026)[0]).toBe(SNAPSHOT_CAVEAT_TEMPLATE.replace("{years}", "2026"));
  });

  it("changes only the snapshot line when the edition changes", () => {
    expect(editionCaveats(2025).slice(1)).toEqual([CAVEAT_THE_PARTIAL, CAVEAT_ARWU_PARTIAL]);
    expect(editionCaveats(2025).slice(1)).toEqual(editionCaveats(2026).slice(1));
    expect(editionCaveats(2025)[0]).not.toBe(editionCaveats(2026)[0]);
  });

  it("leaves the warehouse-wide STANDARD_CAVEATS naming every edition held", () => {
    expect(STANDARD_CAVEATS[0]).toContain("2025 and 2026");
  });
});
