import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import UniversityDetailPage from "@/app/universities/[slug]/page";
import UniversityNotFound from "@/app/universities/[slug]/not-found";
import { fetchJson } from "@/lib/api";
import { ApiError } from "@/lib/apiError";

jest.mock("next/link", () => {
  return function MockLink({ children, href, ...props }: { children: ReactNode; href: string }) {
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  };
});

// The real notFound() throws an internal Next.js error; a sentinel makes "it was called" observable.
const NOT_FOUND = new Error("NEXT_NOT_FOUND (test)");
jest.mock("next/navigation", () => ({
  notFound: jest.fn(() => {
    throw NOT_FOUND;
  }),
}));

jest.mock("@/lib/api", () => ({ fetchJson: jest.fn() }));
jest.mock("@/components/ShortlistButton", () => function MockShortlistButton() {
  return null;
});
jest.mock("@/components/YearSelector", () => ({
  YearSelector: () => <div data-testid="year-selector" />,
  YearSelectorFallback: () => null,
}));

const mockedFetchJson = fetchJson as jest.MockedFunction<typeof fetchJson>;

function renderPage(slug = "no-such-university") {
  return UniversityDetailPage({
    params: Promise.resolve({ slug }),
    searchParams: Promise.resolve({}),
  });
}

describe("University detail page when the university cannot be shown", () => {
  let consoleError: jest.SpyInstance;

  beforeEach(() => {
    mockedFetchJson.mockReset();
    consoleError = jest.spyOn(console, "error").mockImplementation(() => undefined);
  });
  afterEach(() => consoleError.mockRestore());

  it("hands an API 404 to Next's not-found handling", async () => {
    mockedFetchJson.mockRejectedValue(new ApiError(404));

    await expect(renderPage()).rejects.toBe(NOT_FOUND);
  });

  it.each([
    ["the API fails", () => new ApiError(503)],
    ["the API is not running", () => new TypeError("fetch failed")],
  ])("does not call the university missing when %s", async (_case, error) => {
    mockedFetchJson.mockRejectedValue(error());

    render(await renderPage());

    expect(
      screen.getByText("Unable to load university details. Please confirm the API server is running.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/could not be located in our database/)).not.toBeInTheDocument();
    expect(consoleError).toHaveBeenCalledWith("Detail fetch failed", expect.anything());
  });

  it("does not call the university missing when the API answers without success", async () => {
    mockedFetchJson.mockResolvedValue({ success: false, data: null } as never);

    render(await renderPage());

    expect(
      screen.getByText("Unable to load university details. Please confirm the API server is running.")
    ).toBeInTheDocument();
  });

  it("says the university is not in the database on the not-found page", () => {
    render(<UniversityNotFound />);

    expect(screen.getByText("University Not Found")).toBeInTheDocument();
    expect(screen.getByText("This university could not be located in our database.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Rankings" })).toHaveAttribute("href", "/");
  });
});

describe("fetchJson", () => {
  const realFetch = global.fetch;
  afterEach(() => {
    global.fetch = realFetch;
  });

  it("rejects with the HTTP status, so callers can tell 404 from a failure", async () => {
    const { fetchJson: realFetchJson } = jest.requireActual<typeof import("@/lib/api")>("@/lib/api");
    // jsdom has no Response; fetchJson reads only ok and status before it throws.
    global.fetch = jest.fn(async () => ({ ok: false, status: 404 })) as unknown as typeof fetch;

    const failure = await realFetchJson("/api/v1/universities/by-slug/1").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).status).toBe(404);
    expect((failure as ApiError).message).toBe("Request failed with status 404");
  });
});
