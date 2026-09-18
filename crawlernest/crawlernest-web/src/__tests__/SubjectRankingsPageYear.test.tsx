import { render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";

import { SubjectRankingsPageContent } from "@/app/subject-rankings/page";
import { CAVEAT_SUBJECT_QS_ONLY, editionCaveats } from "@/lib/caveatMessages";

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

/** Subject tables are held for 2026 only, so 2025 legitimately answers with nothing. */
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

  it("names the edition that holds no subject rankings instead of showing another one's", async () => {
    render(<SubjectRankingsPageContent rankingYear={2025} />);

    expect(await screen.findByText("No 2025 subject rankings are held for this selection.")).toBeInTheDocument();
    await waitFor(() => expect(requestedYears()).toContain("2025"));
    expect(screen.queryByRole("link", { name: "MIT" })).not.toBeInTheDocument();
    // Not "2026 · QS": the header names the edition asked for.
    expect(screen.getByText(/2025 edition · QS/)).toBeInTheDocument();
  });

  it("discloses the edition shown, and that subject rankings are QS-only", async () => {
    render(<SubjectRankingsPageContent rankingYear={2025} />);

    const banner = await screen.findByRole("note", { name: "Data caveats" });
    await waitFor(() => expect(within(banner).getByText(editionCaveats(2025)[0])).toBeInTheDocument());
    expect(within(banner).getByText(CAVEAT_SUBJECT_QS_ONLY)).toBeInTheDocument();
    expect(within(banner).queryByText(editionCaveats(2026)[0])).not.toBeInTheDocument();
  });

  it("keeps a non-default edition on the links to university pages", async () => {
    answerFor(2025);
    render(<SubjectRankingsPageContent rankingYear={2025} />);
    expect(await screen.findByRole("link", { name: "MIT" })).toHaveAttribute("href", "/universities/mit?year=2025");
  });
});
