import { render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";

import { ComparePageContent } from "@/app/compare/page";
import { CAVEAT_RANK_CHANGE, editionCaveats } from "@/lib/caveatMessages";

jest.mock("next/link", () => {
  return function MockLink({ children, href, ...props }: { children: ReactNode; href: string }) {
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  };
});

const SHORTLIST = [
  { canonicalUniversityId: 1, universityName: "Alpha University", country: "A", aggregatedRank: 10, slug: "alpha" },
  { canonicalUniversityId: 2, universityName: "Beta University", country: "B", aggregatedRank: 20, slug: "beta" },
];

function university(id: number, name: string, withDelta: boolean) {
  return {
    canonicalUniversityId: id,
    universityName: name,
    country: "A",
    aggregatedRank: id * 10,
    aggregatedScore: 80,
    ieltsMin: null,
    sourceRanks: { QS: id * 10 },
    sourceRankings: [
      {
        source: "QS",
        year: 2026,
        rank: id * 10,
        rankDisplay: String(id * 10),
        score: 80,
        rankDelta: withDelta
          ? { priorYear: 2025, currentYear: 2026, priorRankDisplay: "15", value: -5, min: -5, max: -5, direction: "up" }
          : null,
        rankDeltaReason: withDelta ? null : "single_year_dataset",
      },
    ],
    dataCompleteness: { hasAggregatedRank: true, hasIeltsRequirement: false, availableSourceCount: 1, sourceCoverageRatio: 0.33, coverageRatio: 0.33 },
    aggregationMethodVersion: "test",
    evidenceSummary: { availableSourceCount: 1, bestRank: id * 10, worstRank: id * 10, spread: 0, agreementLevel: "limited", note: "One source." },
    trustScore: 50,
    trustLevel: "medium",
    trustExplain: { sources: {}, coverageScore: 0, consistencyScore: 0, stdDeviation: 0, notes: [] },
    warnings: [],
  };
}

function comparison(year: number) {
  // Only the newer edition has a prior edition to move from.
  const withDelta = year === 2026;
  return {
    success: true,
    data: {
      summary: `Summary for ${year}.`,
      order: ["Alpha University", "Beta University"],
      comparison: {
        universities: {
          "Alpha University": university(1, "Alpha University", withDelta),
          "Beta University": university(2, "Beta University", withDelta),
        },
        decisionFactors: [],
      },
    },
  };
}

const fetchMock = jest.fn();

describe("ComparePageContent edition", () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem("crawlernest_shortlist", JSON.stringify(SHORTLIST));
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (_url: string, init: { body: string }) => {
      const { rankingYear } = JSON.parse(init.body) as { rankingYear: number };
      return { ok: true, json: async () => comparison(rankingYear) };
    });
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  function requestedYears(): number[] {
    return fetchMock.mock.calls.map(([, init]) => (JSON.parse(init.body) as { rankingYear: number }).rankingYear);
  }

  it("sends the selected edition and discloses that edition only", async () => {
    render(<ComparePageContent rankingYear={2025} />);
    await screen.findByText("Summary for 2025.");
    expect(requestedYears()).toEqual([2025]);

    const banner = screen.getByRole("note", { name: "Data caveats" });
    expect(within(banner).getByText(editionCaveats(2025)[0])).toBeInTheDocument();
    // 2025 has no held prior edition, so no movement is shown and the rank-change caveat stays out.
    expect(within(banner).queryByText(CAVEAT_RANK_CHANGE)).not.toBeInTheDocument();
    expect(screen.getByText("2025 edition")).toBeInTheDocument();
  });

  it("refetches on an edition change and swaps the caveats with the cards", async () => {
    const { rerender } = render(<ComparePageContent rankingYear={2025} />);
    await screen.findByText("Summary for 2025.");

    rerender(<ComparePageContent rankingYear={2026} />);
    await screen.findByText("Summary for 2026.");
    expect(requestedYears()).toEqual([2025, 2026]);

    await waitFor(() => {
      const banner = screen.getByRole("note", { name: "Data caveats" });
      expect(within(banner).getByText(editionCaveats(2026)[0])).toBeInTheDocument();
      expect(within(banner).getByText(CAVEAT_RANK_CHANGE)).toBeInTheDocument();
    });
    expect(screen.queryByText(editionCaveats(2025)[0])).not.toBeInTheDocument();
  });
});
