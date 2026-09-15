import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";

import UniversityDetailPage from "@/app/universities/[slug]/page";
import { fetchJson } from "@/lib/api";
import { CAVEAT_RANK_CHANGE, editionCaveats } from "@/lib/caveatMessages";
import type { UniversityDetail } from "@/types/university";

jest.mock("next/link", () => {
  return function MockLink({ children, href, ...props }: { children: ReactNode; href: string }) {
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  };
});

jest.mock("@/lib/api", () => ({ fetchJson: jest.fn() }));
// Client components with their own tests; here they only need to render.
jest.mock("@/components/ShortlistButton", () => function MockShortlistButton() {
  return null;
});
jest.mock("@/components/YearSelector", () => ({
  YearSelector: () => <div data-testid="year-selector" />,
  YearSelectorFallback: () => null,
}));

const mockedFetchJson = fetchJson as jest.MockedFunction<typeof fetchJson>;

const NO_ADMISSIONS = {
  hasData: false,
  degreeLevelCount: 0,
  summary: {
    degreeLevel: null, ieltsRequirement: null, toeflRequirement: null, duolingoRequirement: null,
    gpaRequirement: null, applicationDeadline: null, sourceUrl: null,
  },
  byDegreeLevel: [],
  caveats: [],
};

function detail(overrides: Partial<UniversityDetail>): UniversityDetail {
  return {
    canonicalUniversityId: 1,
    slug: "mit",
    universityName: "Massachusetts Institute of Technology",
    country: "United States",
    aggregatedRanking: { displayRank: 4, compositeScore: 97, rankingYear: 2025, aggregationMethodVersion: "v2" },
    sourceRankings: [
      { source: "QS", year: 2025, rank: 1, rankDisplay: "1", score: 100, rankDelta: null, rankDeltaReason: "single_year_dataset" },
    ],
    admissionRequirements: NO_ADMISSIONS,
    dataQuality: null,
    rankingYear: 2025,
    ...overrides,
  };
}

function answer(university: UniversityDetail, subjectItems: unknown[] = []) {
  mockedFetchJson.mockImplementation(async (path: string) => {
    if (path.includes("/subject-rankings")) {
      return { success: true, data: { items: subjectItems } } as never;
    }
    return { success: true, data: university } as never;
  });
}

async function renderPage(search: Record<string, string> = {}) {
  const ui = await UniversityDetailPage({
    params: Promise.resolve({ slug: "mit" }),
    searchParams: Promise.resolve(search),
  });
  return render(ui);
}

function requestedPaths(): string[] {
  return mockedFetchJson.mock.calls.map(([path]) => String(path));
}

describe("University detail page edition", () => {
  beforeEach(() => mockedFetchJson.mockReset());

  it("reads the university and its subject rankings for the selected edition", async () => {
    answer(detail({}));
    await renderPage({ year: "2025" });

    expect(requestedPaths()).toEqual([
      "/api/v1/universities/by-slug/mit?year=2025",
      "/api/v1/universities/1/subject-rankings?year=2025",
    ]);
    expect(screen.getByText("2025 edition")).toBeInTheDocument();
    expect(screen.getByTestId("year-selector")).toBeInTheDocument();
  });

  it("discloses that edition only, and keeps it on the links out", async () => {
    answer(detail({}));
    await renderPage({ year: "2025" });

    const banner = screen.getByRole("note", { name: "Data caveats" });
    expect(within(banner).getByText(editionCaveats(2025)[0])).toBeInTheDocument();
    // 2025 has no held prior edition: no movement, so no rank-change caveat.
    expect(within(banner).queryByText(CAVEAT_RANK_CHANGE)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Rankings" })).toHaveAttribute("href", "/?year=2025");
    expect(screen.getByRole("link", { name: "Check Admission Odds" })).toHaveAttribute("href", "/recommendations?year=2025");
  });

  it("says a university is missing from the edition rather than showing another edition's rank", async () => {
    answer(detail({ aggregatedRanking: null, sourceRankings: [] }));
    await renderPage({ year: "2025" });

    expect(screen.getByText("Not in the 2025 edition held here.")).toBeInTheDocument();
    expect(screen.getByText("No 2025 ranking row is held for this university.")).toBeInTheDocument();
    expect(screen.queryByText(/#N\/A/)).not.toBeInTheDocument();
  });

  it("names the edition when it holds no subject rankings, instead of implying the university has none", async () => {
    answer(detail({}));
    await renderPage({ year: "2025" });
    expect(screen.getByText("No 2025 subject rankings are held for this university.")).toBeInTheDocument();
  });

  it("reads the default edition with plain links when the URL names none or an unheld one", async () => {
    const searches: Record<string, string>[] = [{}, { year: "2019" }];
    for (const search of searches) {
      mockedFetchJson.mockReset();
      answer(detail({ rankingYear: 2026, aggregatedRanking: { displayRank: 2, compositeScore: 98, rankingYear: 2026, aggregationMethodVersion: "v2" } }));
      const { unmount } = await renderPage(search);
      expect(requestedPaths()[0]).toBe("/api/v1/universities/by-slug/mit?year=2026");
      expect(screen.getByRole("link", { name: "Rankings" })).toHaveAttribute("href", "/");
      unmount();
    }
  });
});
