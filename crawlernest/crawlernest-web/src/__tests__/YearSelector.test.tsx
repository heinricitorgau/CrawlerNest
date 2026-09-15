import { fireEvent, render, screen, within } from "@testing-library/react";

import { CaveatBanner } from "@/components/CaveatBanner";
import { YearSelector } from "@/components/YearSelector";

const push = jest.fn();
let currentQuery = "";
let currentPath = "/compare";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: jest.fn() }),
  usePathname: () => currentPath,
  useSearchParams: () => new URLSearchParams(currentQuery),
}));

describe("YearSelector", () => {
  beforeEach(() => {
    push.mockReset();
    currentQuery = "";
    currentPath = "/compare";
  });

  it("offers only the held editions, newest first, labelled for assistive technology", () => {
    render(<YearSelector />);
    const select = screen.getByLabelText("Ranking edition");
    expect(within(select).getAllByRole("option").map((option) => option.textContent)).toEqual(["2026", "2025"]);
    expect(select).toHaveValue("2026");
  });

  it("shows the edition a shared link names", () => {
    currentQuery = "year=2025";
    render(<YearSelector variant="nav" />);
    expect(screen.getByLabelText("Edition")).toHaveValue("2025");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("writes the edition to the URL, keeping other filters and dropping the page number", () => {
    currentPath = "/";
    currentQuery = "scope=region&region=Europe&page=4&year=2026";
    render(<YearSelector />);
    fireEvent.change(screen.getByLabelText("Ranking edition"), { target: { value: "2025" } });

    expect(push).toHaveBeenCalledTimes(1);
    const [href, options] = push.mock.calls[0];
    const url = new URL(href, "http://localhost");
    expect(url.pathname).toBe("/");
    expect(url.searchParams.get("year")).toBe("2025");
    expect(url.searchParams.get("scope")).toBe("region");
    expect(url.searchParams.get("region")).toBe("Europe");
    expect(url.searchParams.has("page")).toBe(false);
    expect(options).toEqual({ scroll: false });
  });

  it("says so when a link names an edition that is not held, instead of silently showing another", () => {
    currentQuery = "year=2019";
    render(<YearSelector />);
    const select = screen.getByLabelText("Ranking edition");
    expect(select).toHaveValue("2026");
    const note = screen.getByRole("status");
    expect(note).toHaveTextContent("No 2019 edition is held. Showing 2026.");
    expect(select).toHaveAttribute("aria-describedby", note.id);
  });
});

describe("CaveatBanner", () => {
  it("renders nothing when there is nothing to disclose", () => {
    const { container } = render(<CaveatBanner caveats={[null, undefined, "  "]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders each caveat verbatim, once, in order", () => {
    render(<CaveatBanner caveats={["First caveat.", null, "Second caveat.", "First caveat."]} />);
    const note = screen.getByRole("note", { name: "Data caveats" });
    expect(within(note).getAllByRole("listitem").map((item) => item.textContent)).toEqual(["First caveat.", "Second caveat."]);
  });
});
