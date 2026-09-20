import { render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";

import { SubjectRankingsPageContent } from "@/app/subject-rankings/page";
import { CAVEAT_SUBJECT_QS_ONLY, subjectEditionCaveats } from "@/lib/caveatMessages";
import { SUBJECT_DATASET_YEARS } from "@/lib/datasetScope";

jest.mock("next/link", () => {
  return function MockLink({ children, href, ...props }: { children: ReactNode; href: string }) {
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  };
});

const SUBJECTS = { success: true, data: { items: [{ subjectKey: "computer-science", subjectName: "Computer Science" }] } };

function row(year: number) {
  return {
    subjectKey: "computer-science",
    subjectName: "Computer Science",
    rankingYear: year,
    canonicalUniversityId: 1,
    canonicalSlug: "mit",
    universityName: "MIT",
    countryName: "United States",
    rankPosition: 1,
    rankDisplay: "1",
    score: 100,
    sourceCode: "QS",
  };
}

const fetchMock = jest.fn();

/**
 * Subject tables are held for 2026 only, so every other edition legitimately
 * answers with nothing. The mock still returns {@code source: "QS"} in that
 * case, because the API does: the page must not take that as licence to print
 * "QS" beside an edition with no QS subject row in it.
 */
function answerFor(heldYear: number) {
  fetchMock.mockImplementation(async (url: string) => {
    if (String(url).includes("/subjects")) {
      return { ok: true, json: async () => SUBJECTS };
    }
    const year = Number(new URLSearchParams(String(url).split("?")[1]).get("year"));
    const items = year === heldYear ? [row(year)] : [];
    return {
      ok: true,
      json: async () => ({
        success: true,
        data: { items, metadata: { year, source: "QS", totalCount: items.length } },
      }),
    };
  });
}

function requestedYears(): string[] {
  return fetchMock.mock.calls
    .map(([url]) => String(url))
    .filter((url) => !url.includes("/subjects"))
    .map((url) => new URLSearchParams(url.split("?")[1]).get("year") ?? "");
}

describe("Subject rankings page edition", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    answerFor(2026);
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it("asks for the selected edition and shows its rows", async () => {
    render(<SubjectRankingsPageContent rankingYear={2026} />);
    expect(await screen.findByRole("link", { name: "MIT" })).toHaveAttribute("href", "/universities/mit");
    await waitFor(() => expect(requestedYears()).toContain("2026"));
    expect(requestedYears()).not.toContain("2025");
  });

  it("names the source only for an edition that has one", async () => {
    render(<SubjectRankingsPageContent rankingYear={2026} />);
    await waitFor(() => expect(screen.getByText(/2026 edition · QS/)).toBeInTheDocument());
  });

  describe("an edition with no subject rows at all", () => {
    // 2018 is a released world-ranking edition holding ARWU ranks and no
    // subject table. The page used to answer it with the world-ranking
    // caveats -- "The 2018 edition holds ARWU ranks only" beside "Subject
    // rankings are QS-sourced only" -- and a heading reading "2018 edition · QS".
    it("isolates the year rather than showing another edition's rows", async () => {
      render(<SubjectRankingsPageContent rankingYear={2018} />);

      await waitFor(() => expect(requestedYears()).toContain("2018"));
      expect(requestedYears()).not.toContain("2026");
      expect(screen.queryByRole("link", { name: "MIT" })).not.toBeInTheDocument();
    });

    it("says no subject data is held, and does not attribute a source to it", async () => {
      render(<SubjectRankingsPageContent rankingYear={2018} />);

      expect(
        await screen.findByText(
          "No subject rankings are held for the 2018 edition at all. Subject data covers 2026.",
        ),
      ).toBeInTheDocument();
      expect(screen.getByText(/2018 edition · no subject data held/)).toBeInTheDocument();
      expect(screen.queryByText(/2018 edition · QS/)).not.toBeInTheDocument();
    });

    it("carries the missing-data disclosure and none of the world-ranking ones", async () => {
      render(<SubjectRankingsPageContent rankingYear={2018} />);
      const banner = await screen.findByRole("note", { name: "Data caveats" });

      const [missing] = subjectEditionCaveats(2018);
      expect(within(banner).getByText(missing)).toBeInTheDocument();
      expect(missing).toContain("No subject ranking data is held for the 2018 edition");
      expect(missing).toContain("crawled for 2026 only");

      // The three sentences this page used to show for 2018, all wrong here.
      expect(within(banner).queryByText(/holds ARWU ranks only/)).not.toBeInTheDocument();
      expect(within(banner).queryByText(/point-in-time snapshot of the 2018/)).not.toBeInTheDocument();
      expect(within(banner).queryByText(CAVEAT_SUBJECT_QS_ONLY)).not.toBeInTheDocument();
    });
  });

  it("discloses the snapshot and the QS-only scope for the edition that has data", async () => {
    render(<SubjectRankingsPageContent rankingYear={2026} />);
    const banner = await screen.findByRole("note", { name: "Data caveats" });

    const caveats = subjectEditionCaveats(2026);
    expect(caveats).toHaveLength(2);
    expect(within(banner).getByText(caveats[0])).toBeInTheDocument();
    expect(caveats[0]).toContain("QS subject ranking data");
    expect(within(banner).getByText(CAVEAT_SUBJECT_QS_ONLY)).toBeInTheDocument();
  });

  it("offers only the editions that hold subject rows", () => {
    // The selector's options come from subject coverage, not from every edition
    // the warehouse holds: twelve options with data for one is a control that
    // proposes eleven empty pages.
    expect(SUBJECT_DATASET_YEARS).toEqual([2026]);
  });

  it("keeps a non-default edition on the links to university pages", async () => {
    answerFor(2025);
    render(<SubjectRankingsPageContent rankingYear={2025} />);
    expect(await screen.findByRole("link", { name: "MIT" })).toHaveAttribute("href", "/universities/mit?year=2025");
  });
});
