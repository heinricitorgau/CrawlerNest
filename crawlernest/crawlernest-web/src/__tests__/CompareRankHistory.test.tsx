import { render, screen, waitFor } from "@testing-library/react";
import { CompareRankHistory, linesBySource, shortLabel } from "@/components/CompareRankHistory";
import { LINE_COLORS } from "@/components/RankLinesChart";
import { CAVEAT_RANK_HISTORY } from "@/lib/caveatMessages";
import type { RankHistory } from "@/types/university";

const history = (qsRank: number | null, theRank: number): RankHistory => ({
  years: [2025, 2026],
  series: [
    {
      source: "QS", rankedEditions: qsRank == null ? 0 : 2,
      points: [2025, 2026].map((year) => qsRank == null
        ? { year, status: "not_in_edition" as const }
        : { year, status: "ranked" as const, rankLower: qsRank, rankUpper: qsRank, rankDisplay: String(qsRank) }),
    },
    {
      source: "THE", rankedEditions: 2,
      points: [2025, 2026].map((year) => ({ year, status: "ranked" as const, rankLower: theRank, rankUpper: theRank, rankDisplay: String(theRank) })),
    },
  ],
  caveats: [CAVEAT_RANK_HISTORY],
});

const universities = [
  { canonicalUniversityId: 3, universityName: "University of Oxford" },
  { canonicalUniversityId: 60, universityName: "Universiti Malaya (UM)" },
];

describe("CompareRankHistory", () => {
  it("labels universities briefly and keeps the full name in every sentence", () => {
    expect(shortLabel("Universiti Malaya (UM)")).toBe("UM");
    expect(shortLabel("University of California, Los Angeles")).toBe("UCLA");
    expect(shortLabel("ETH Zurich")).toBe("ETH Zurich");
    expect(shortLabel("University of Oxford")).toBe("University of Oxf…");
  });

  it("draws one chart per source with one line per university, colour by selection order", () => {
    const charts = linesBySource(universities, [history(4, 1), history(null, 201)]);
    expect(charts.map((c) => c.source)).toEqual(["QS", "THE"]);
    const the = charts[1].lines;
    expect(the.map((l) => [l.key, l.color])).toEqual([["3", LINE_COLORS[0]], ["60", LINE_COLORS[1]]]);
    expect(the[1].describe(the[1].points[0])).toBe("Universiti Malaya (UM) — THE 2025: 201");
    expect(charts[0].lines[1].describe(charts[0].lines[1].points[0])).toBe(
      "Universiti Malaya (UM) — Not in the QS 2025 edition as held here"
    );
  });

  it("fetches each history through the proxy and renders the charts with the API's caveats", async () => {
    const responses: Record<string, RankHistory> = { "3": history(4, 1), "60": history(null, 201) };
    global.fetch = jest.fn(async (url: string) => {
      const id = String(url).match(/universities\/(\d+)\//)![1];
      return { ok: true, json: async () => ({ success: true, data: responses[id] }) };
    }) as unknown as typeof fetch;

    render(<CompareRankHistory universities={universities} />);
    await waitFor(() => expect(screen.getAllByRole("img")).toHaveLength(2));
    expect(global.fetch).toHaveBeenCalledWith("/api/universities/3/rank-history");
    expect(screen.getByText(CAVEAT_RANK_HISTORY)).toBeInTheDocument();
  });

  it("renders nothing for fewer than two universities", () => {
    const { container } = render(<CompareRankHistory universities={[universities[0]]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
