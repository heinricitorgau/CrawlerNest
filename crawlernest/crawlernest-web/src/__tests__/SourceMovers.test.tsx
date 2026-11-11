import { render, screen, waitFor } from "@testing-library/react";
import { SourceMovers, describeCounts, type SourceMoversData } from "@/components/SourceMovers";
import { CAVEAT_RANK_CHANGE } from "@/lib/caveatMessages";

const base: SourceMoversData = {
  source: "THE", ranking_year: 2026, prior_year: 2025,
  risers: [{ canonicalUniversityId: 1, universityName: "Alpha University", slug: "alpha", country: "X", priorRankDisplay: "40", rankDisplay: "30", rankDelta: -10 }],
  fallers: [{ canonicalUniversityId: 2, universityName: "Beta University", slug: null, country: null, priorRankDisplay: "50", rankDisplay: "58", rankDelta: 8 }],
  counts: { exact: 1200, banded: 300, entity_changed: 4, only_in_2026: 60, only_in_2025: 10 },
  caveats: [CAVEAT_RANK_CHANGE],
};

function answer(data: SourceMoversData) {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({ success: true, data }) })) as unknown as typeof fetch;
}

describe("SourceMovers", () => {
  it("says what every count is, and never lists banded or withheld rows", () => {
    const lines = describeCounts(base);
    expect(lines[0]).toBe("1,200 universities compared on exact ranks");
    expect(lines).toContain("300 with a printed band in one edition (an interval, not listed)");
    expect(lines.some((l) => l.startsWith("4 not compared: The institution or its entry"))).toBe(true);
    expect(lines).toContain("60 ranked here in 2026 but not in 2025 as held");
  });

  it("renders risers and fallers with the edition pair, links by slug, and the API's caveats", async () => {
    answer(base);
    render(<SourceMovers />);
    await waitFor(() => expect(screen.getByText("Alpha University")).toBeInTheDocument());
    expect(screen.getByText("Alpha University").closest("a")).toHaveAttribute("href", "/universities/alpha?year=2026");
    expect(screen.getByText("Beta University").closest("a")).toBeNull();
    expect(screen.getByText("compared with the 2025 edition")).toBeInTheDocument();
    expect(screen.getByText(CAVEAT_RANK_CHANGE)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("source=THE&year="));
  });

  it("explains a withheld comparison instead of reaching back to an older edition", async () => {
    answer({ ...base, source: "QS", ranking_year: 2018, prior_year: 2017, withheld_reason: "no_qs_edition_2017",
             risers: [], fallers: [], counts: {} });
    render(<SourceMovers />);
    await waitFor(() => expect(screen.getByText(/No QS edition of 2017 is held here/)).toBeInTheDocument());
    expect(screen.getByText(/It is not compared with an older edition instead/)).toBeInTheDocument();
  });
});
