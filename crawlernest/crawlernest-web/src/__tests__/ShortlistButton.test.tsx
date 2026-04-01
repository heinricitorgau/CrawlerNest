import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ShortlistButton from "@/components/ShortlistButton";

const STORAGE_KEY = "crawlernest_shortlist";

const mockItem = {
  canonicalUniversityId: 42,
  universityName: "MIT",
  country: "USA",
  aggregatedRank: 1,
  slug: "massachusetts-institute-of-technology",
};

beforeEach(() => {
  localStorage.clear();
});

describe("ShortlistButton", () => {
  it("renders '+ Shortlist' when item is not in shortlist", () => {
    render(<ShortlistButton item={mockItem} />);
    expect(screen.getByText("+ Shortlist")).toBeInTheDocument();
  });

  it("renders '✓ Shortlisted' when item is already in shortlist", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([mockItem]));
    render(<ShortlistButton item={mockItem} />);
    expect(screen.getByText("✓ Shortlisted")).toBeInTheDocument();
  });

  it("adds item to localStorage when clicked from empty state", () => {
    render(<ShortlistButton item={mockItem} />);
    fireEvent.click(screen.getByText("+ Shortlist"));

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    expect(stored).toHaveLength(1);
    expect(stored[0].canonicalUniversityId).toBe(42);
  });

  it("removes item from localStorage when clicked from shortlisted state", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([mockItem]));
    render(<ShortlistButton item={mockItem} />);
    fireEvent.click(screen.getByText("✓ Shortlisted"));

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    expect(stored).toHaveLength(0);
  });

  it("toggles button label after click", () => {
    render(<ShortlistButton item={mockItem} />);
    const btn = screen.getByText("+ Shortlist");
    fireEvent.click(btn);
    expect(screen.getByText("✓ Shortlisted")).toBeInTheDocument();
  });

  it("does not affect other items in shortlist when removing", () => {
    const otherItem = { ...mockItem, canonicalUniversityId: 99, universityName: "Oxford" };
    localStorage.setItem(STORAGE_KEY, JSON.stringify([mockItem, otherItem]));
    render(<ShortlistButton item={mockItem} />);
    fireEvent.click(screen.getByText("✓ Shortlisted"));

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    expect(stored).toHaveLength(1);
    expect(stored[0].canonicalUniversityId).toBe(99);
  });
});
