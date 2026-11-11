import { fireEvent, render, screen } from "@testing-library/react";
import { RankHistoryChart, cellText, describePoint, lineSegments, rankDomain } from "@/components/RankHistoryChart";
import { CAVEAT_RANK_HISTORY } from "@/lib/caveatMessages";
import type { RankHistory, RankHistoryPoint } from "@/types/university";

const ranked = (year: number, lower: number, upper: number | null = lower, extra: Partial<RankHistoryPoint> = {}): RankHistoryPoint => ({
  year, status: "ranked", rankLower: lower, rankUpper: upper, rankDisplay: upper === lower ? String(lower) : upper == null ? `${lower}+` : `${lower}-${upper}`,
  archived: false, suspiciousMerge: false, sourceIdentityChanged: false, ...extra,
});

const history: RankHistory = {
  years: [2016, 2017, 2018, 2019],
  series: [
    { source: "QS", rankedEditions: 2, points: [ranked(2016, 50, 50, { archived: true }), { year: 2017, status: "edition_not_held" }, ranked(2018, 40), ranked(2019, 45)] },
    { source: "THE", rankedEditions: 2, points: [ranked(2016, 201, 250), { year: 2017, status: "not_in_edition" }, ranked(2018, 180), ranked(2019, 170, 170, { sourceIdentityChanged: true })] },
    { source: "ARWU", rankedEditions: 0, points: [2016, 2017, 2018, 2019].map((year) => ({ year, status: "not_in_edition" as const })) },
  ],
  caveats: [CAVEAT_RANK_HISTORY],
};

describe("RankHistoryChart", () => {
  it("never draws a line across a gap or a change of source entry", () => {
    const qs = lineSegments(history.series[0].points).map((s) => [s.from.year, s.to.year]);
    expect(qs).toEqual([[2018, 2019]]);
    // THE 2018 -> 2019 is two ranked editions, but the source entry changed between them.
    expect(lineSegments(history.series[1].points)).toEqual([]);
  });

  it("fits the log domain to the ranks shown, open bands included", () => {
    const [lo, hi] = rankDomain(history.series);
    expect(lo).toBeLessThan(40);
    expect(lo).toBeGreaterThan(20);
    expect(hi).toBeGreaterThan(250);
    expect(rankDomain([history.series[2]])).toEqual([1, 10]);
  });

  it("says which kind of gap each one is, and never that the source declined to rank", () => {
    expect(describePoint("QS", { year: 2017, status: "edition_not_held" })).toBe("No QS 2017 edition is held here");
    expect(describePoint("THE", { year: 2017, status: "not_in_edition" })).toBe("Not in the THE 2017 edition as held here");
    expect(describePoint("QS", ranked(2016, 50, 50, { archived: true }))).toBe("QS 2016: 50 (from an Internet Archive capture)");
    expect(cellText(ranked(2016, 201, 250))).toBe("201-250");
    expect(cellText({ year: 2017, status: "edition_not_held" })).toBe("no edition held");
  });

  it("renders the table view, the coverage strip and the API's caveats verbatim", () => {
    render(<RankHistoryChart history={history} />);
    expect(screen.getByText(CAVEAT_RANK_HISTORY)).toBeInTheDocument();
    expect(screen.getByText("50*")).toBeInTheDocument();
    expect(screen.getAllByText("not in edition").length).toBeGreaterThan(0);
    expect(screen.getAllByText("No QS 2017 edition is held here").length).toBeGreaterThan(0);
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", expect.stringContaining("logarithmic"));
  });

  it("shows every source's state for an edition on hover", () => {
    const { container } = render(<RankHistoryChart history={history} />);
    const columns = container.querySelectorAll('rect[fill="transparent"]');
    fireEvent.mouseEnter(columns[1]);
    const tooltip = screen.getByRole("status");
    expect(tooltip).toHaveTextContent("2017 edition");
    expect(tooltip).toHaveTextContent("No QS 2017 edition is held here");
    expect(tooltip).toHaveTextContent("Not in the THE 2017 edition as held here");
  });

  it("says so plainly when no source ranks the university in any edition", () => {
    render(<RankHistoryChart history={{ ...history, series: [history.series[2]] }} />);
    expect(screen.getByText(/No source rank is held for this university in any edition here/)).toBeInTheDocument();
    expect(screen.getByText(CAVEAT_RANK_HISTORY)).toBeInTheDocument();
  });
});
