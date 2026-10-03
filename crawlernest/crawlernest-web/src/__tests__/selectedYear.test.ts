/**
 * @jest-environment node
 */
import { SNAPSHOT_CAVEAT_TEMPLATE, CAVEAT_ARWU_PARTIAL, CAVEAT_THE_PARTIAL, STANDARD_CAVEATS, archiveEditionCaveat, editionCaveats, editionSourceCoverageCaveat } from "@/lib/caveatMessages";
import { DATASET_ARCHIVE_EDITIONS, DATASET_YEARS, DEFAULT_RANKING_YEAR, hrefForEdition, hrefWithYear, resolveSelectedYear } from "@/lib/datasetScope";
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
    for (const raw of ["1999", "2027", "20250", "2025abc", "abc", "-2025"]) {
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

describe("hrefForEdition", () => {
  it("writes only a non-default edition into a link", () => {
    expect(hrefForEdition("/universities/mit", DEFAULT_RANKING_YEAR)).toBe("/universities/mit");
    expect(hrefForEdition("/universities/mit", 2025)).toBe("/universities/mit?year=2025");
  });
});

describe("isYearAwarePath", () => {
  it("covers the pages whose data depends on the edition and no others", () => {
    for (const path of ["/", "/rankings", "/recommendations", "/compare", "/subject-rankings", "/universities/mit", "/universities/mit/"]) {
      expect(isYearAwarePath(path)).toBe(true);
    }
    for (const path of ["/about", "/analytics", "/universities", "/universities/mit/sources", "/rankings/extra"]) {
      expect(isYearAwarePath(path)).toBe(false);
    }
  });
});

describe("editionCaveats", () => {
  it("names only the edition a page shows, and the sources it holds", () => {
    const shown = editionCaveats(2025);
    expect(shown[0]).toBe(
      SNAPSHOT_CAVEAT_TEMPLATE.replace("{source}", "QS, THE and ARWU").replace("{years}", "2025"),
    );
    expect(shown[0]).not.toContain("2026");
    expect(editionCaveats(2026)[0]).toBe(
      SNAPSHOT_CAVEAT_TEMPLATE.replace("{source}", "QS, THE and ARWU").replace("{years}", "2026"),
    );
  });

  it("names THE and ARWU, not QS, for an edition QS does not cover", () => {
    // The defect the 2015-2024 ARWU release had to fix, and still true for QS 2015,
    // 2017 and 2021: editionCaveats(2017) must not render "QS ranking data is a
    // point-in-time snapshot of the 2017 published tables" onto a table with no QS rank.
    const shown = editionCaveats(2017);
    expect(shown[0]).toBe(
      SNAPSHOT_CAVEAT_TEMPLATE.replace("{source}", "THE and ARWU").replace("{years}", "2017"),
    );
    expect(shown.join(" ")).not.toContain("QS ranking data");
    expect(shown).toContain(editionSourceCoverageCaveat(2017));
    expect(shown).toContain(CAVEAT_THE_PARTIAL);
    expect(shown).toContain(CAVEAT_ARWU_PARTIAL);
    expect(shown.some((c) => c.includes("Internet Archive"))).toBe(false);
  });

  it("says which sources an edition is missing, and nothing when it holds them all", () => {
    const caveat = editionSourceCoverageCaveat(2017);
    expect(caveat).toContain("The 2017 edition holds THE and ARWU ranks only");
    expect(caveat).toContain("No QS rank exists");
    // Two of three sources are present, so it must not claim a single source.
    expect(caveat).not.toContain("one source");
    expect(editionSourceCoverageCaveat(2018)).toBeNull();
    expect(editionSourceCoverageCaveat(2026)).toBeNull();
  });

  it("discloses an archive-sourced edition, and only that", () => {
    const shown = editionCaveats(2024);
    expect(shown).toEqual([
      SNAPSHOT_CAVEAT_TEMPLATE.replace("{source}", "QS, THE and ARWU").replace("{years}", "2024"),
      archiveEditionCaveat("QS", 2024),
      CAVEAT_THE_PARTIAL,
      CAVEAT_ARWU_PARTIAL,
    ]);
    expect(shown[1]).toContain("2026-03-29");
    expect(shown[1]).toContain("lower bound");
    expect(shown[1]).toContain("2025 and 2026");
    expect(shown[1]).not.toContain("{");
    expect(archiveEditionCaveat("QS", 2026)).toBeNull();
    expect(archiveEditionCaveat("THE", 2024)).toBeNull();
    expect(editionCaveats(2026).some((c) => c.includes("Internet Archive"))).toBe(false);
    expect(STANDARD_CAVEATS.some((c) => c.includes("Internet Archive"))).toBe(false);
  });

  it("gives every archive edition its line and no other edition one", () => {
    for (const year of DATASET_YEARS) {
      const has = editionCaveats(year).some((c) => c.includes("Internet Archive"));
      expect(has).toBe(year in DATASET_ARCHIVE_EDITIONS.QS);
    }
  });

  it("changes only the snapshot line between two editions holding the same sources", () => {
    expect(editionCaveats(2025).slice(1)).toEqual([CAVEAT_THE_PARTIAL, CAVEAT_ARWU_PARTIAL]);
    expect(editionCaveats(2025).slice(1)).toEqual(editionCaveats(2026).slice(1));
    expect(editionCaveats(2025)[0]).not.toBe(editionCaveats(2026)[0]);
  });

  it("leaves the warehouse-wide STANDARD_CAVEATS naming every edition held", () => {
    expect(STANDARD_CAVEATS[0]).toContain("2025 and 2026");
  });
});
