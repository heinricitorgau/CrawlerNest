import { render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";

import { RecommendationPageContent } from "@/app/recommendations/page";
import { fetchAppJson } from "@/lib/api";
import { editionCaveats } from "@/lib/caveatMessages";

jest.mock("next/link", () => {
  return function MockLink({ children, href, ...props }: { children: ReactNode; href: string }) {
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  };
});

jest.mock("@/lib/api", () => ({
  fetchAppJson: jest.fn(),
}));

const mockedFetchAppJson = fetchAppJson as jest.MockedFunction<typeof fetchAppJson>;
const STORAGE_KEY = "crawlernest_recommendation_flow";

function response() {
  return {
    success: true,
    data: { reach: [], target: [], safety: [] },
    metadata: {
      admission_caveats: [
        "Admission requirements were read from university pages whose fetch date was not recorded. They were extracted on 2026-08-22, the pages may be older than that, and they may not reflect the current year's entry conditions.",
      ],
    },
  };
}

function requestedYears(): string[] {
  return mockedFetchAppJson.mock.calls.map(([url]) => new URLSearchParams(String(url).split("?")[1]).get("rankingYear") ?? "");
}

describe("RecommendationPageContent edition", () => {
  beforeEach(() => {
    localStorage.clear();
    mockedFetchAppJson.mockReset();
    mockedFetchAppJson.mockResolvedValue(response());
    // A restored flow fetches on mount, which is the simplest way to have results.
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ selectedPlan: null, selectedScenarioKey: null, currentFocus: null, profileDraft: {} }),
    );
  });

  it("asks the API for the selected edition", async () => {
    render(<RecommendationPageContent rankingYear={2025} />);
    await waitFor(() => expect(mockedFetchAppJson).toHaveBeenCalledTimes(1));
    expect(requestedYears()).toEqual(["2025"]);
  });

  it("re-runs the request when the edition changes, and the caveats follow the rows", async () => {
    const { rerender } = render(<RecommendationPageContent rankingYear={2025} />);
    const banner = await screen.findByRole("note", { name: "Data caveats" });
    expect(within(banner).getByText(editionCaveats(2025)[0])).toBeInTheDocument();
    // The admission caveat from the API renders verbatim, and the layout holds it.
    expect(within(banner).getByText(/fetch date was not recorded/)).toBeInTheDocument();

    rerender(<RecommendationPageContent rankingYear={2026} />);
    await waitFor(() => expect(requestedYears()).toEqual(["2025", "2026"]));
    await waitFor(() =>
      expect(within(screen.getByRole("note", { name: "Data caveats" })).getByText(editionCaveats(2026)[0])).toBeInTheDocument(),
    );
    expect(screen.queryByText(editionCaveats(2025)[0])).not.toBeInTheDocument();
  });

  it("fetches nothing on an edition change before recommendations were first requested", async () => {
    localStorage.clear();
    const { rerender } = render(<RecommendationPageContent rankingYear={2026} />);
    rerender(<RecommendationPageContent rankingYear={2025} />);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(mockedFetchAppJson).not.toHaveBeenCalled();
    expect(screen.queryByRole("note", { name: "Data caveats" })).not.toBeInTheDocument();
  });
});
