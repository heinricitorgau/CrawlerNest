import { act, fireEvent, render, screen } from "@testing-library/react";
import ShortlistButton from "@/components/ShortlistButton";
import { SHORTLIST_STORAGE_KEY, parseShortlist, readShortlist, useShortlist } from "@/lib/shortlistStore";

const mit = { canonicalUniversityId: 42, universityName: "MIT", country: "USA", aggregatedRank: 1, slug: "mit" };
const oxford = { canonicalUniversityId: 3, universityName: "Oxford", country: "UK", aggregatedRank: 2, slug: "oxford" };

function Count() {
  const [items] = useShortlist();
  return <p data-testid="count">{items.length}</p>;
}

beforeEach(() => localStorage.clear());

describe("shortlistStore", () => {
  it("keeps only well-formed items and survives junk", () => {
    expect(parseShortlist(null)).toEqual([]);
    expect(parseShortlist("not json")).toEqual([]);
    expect(parseShortlist('{"a":1}')).toEqual([]);
    expect(parseShortlist(JSON.stringify([mit, { canonicalUniversityId: "x" }, null]))).toEqual([mit]);
  });

  it("returns the same array until the stored text changes", () => {
    localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify([mit]));
    expect(readShortlist()).toBe(readShortlist());
  });

  it("updates every reader on the page when one component toggles", () => {
    render(
      <>
        <ShortlistButton item={mit} />
        <Count />
      </>,
    );
    expect(screen.getByTestId("count")).toHaveTextContent("0");
    fireEvent.click(screen.getByText("+ Shortlist"));
    expect(screen.getByTestId("count")).toHaveTextContent("1");
    expect(JSON.parse(localStorage.getItem(SHORTLIST_STORAGE_KEY)!)).toEqual([mit]);
  });

  it("picks up a change made in another tab", () => {
    render(<Count />);
    act(() => {
      localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify([mit, oxford]));
      window.dispatchEvent(new StorageEvent("storage", { key: SHORTLIST_STORAGE_KEY }));
    });
    expect(screen.getByTestId("count")).toHaveTextContent("2");
  });

  it("renders nothing for an invalid item, without a hooks-order error", () => {
    const { container, rerender } = render(<ShortlistButton item={mit} />);
    rerender(<ShortlistButton item={{ ...mit, canonicalUniversityId: "x" as unknown as number }} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<ShortlistButton item={mit} />);
    expect(screen.getByText("+ Shortlist")).toBeInTheDocument();
  });
});
