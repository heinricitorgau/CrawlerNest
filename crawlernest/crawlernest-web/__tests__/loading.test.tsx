import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import RankingsLoading from "@/app/loading";
import RecommendationsLoading from "@/app/recommendations/loading";
import UniversityDetailLoading from "@/app/universities/[slug]/loading";

describe("RankingsLoading (main page skeleton)", () => {
  it("renders without crashing", () => {
    const { container } = render(<RankingsLoading />);
    expect(container).toBeTruthy();
  });

  it("renders a main element", () => {
    render(<RankingsLoading />);
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("contains animate-pulse skeleton elements", () => {
    const { container } = render(<RankingsLoading />);
    const pulseElements = container.querySelectorAll(".animate-pulse");
    expect(pulseElements.length).toBeGreaterThan(0);
  });

  it("renders table header skeleton", () => {
    const { container } = render(<RankingsLoading />);
    // Should have multiple skeleton rows for the table
    const pulseElements = container.querySelectorAll(".animate-pulse");
    expect(pulseElements.length).toBeGreaterThanOrEqual(10);
  });
});

describe("RecommendationsLoading (recommendations skeleton)", () => {
  it("renders without crashing", () => {
    const { container } = render(<RecommendationsLoading />);
    expect(container).toBeTruthy();
  });

  it("renders a main element", () => {
    render(<RecommendationsLoading />);
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("contains animate-pulse skeleton elements", () => {
    const { container } = render(<RecommendationsLoading />);
    const pulseElements = container.querySelectorAll(".animate-pulse");
    expect(pulseElements.length).toBeGreaterThan(0);
  });

  it("renders form field skeletons", () => {
    const { container } = render(<RecommendationsLoading />);
    // Should have multiple skeleton rows for the form
    const pulseElements = container.querySelectorAll(".animate-pulse");
    expect(pulseElements.length).toBeGreaterThanOrEqual(8);
  });
});

describe("UniversityDetailLoading (detail page skeleton)", () => {
  it("renders without crashing", () => {
    const { container } = render(<UniversityDetailLoading />);
    expect(container).toBeTruthy();
  });

  it("renders a main element", () => {
    render(<UniversityDetailLoading />);
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("contains animate-pulse wrapper", () => {
    const { container } = render(<UniversityDetailLoading />);
    const pulseWrapper = container.querySelector(".animate-pulse");
    expect(pulseWrapper).toBeInTheDocument();
  });

  it("renders skeleton cards for the detail grid", () => {
    const { container } = render(<UniversityDetailLoading />);
    const skeletonDivs = container.querySelectorAll(".rounded-2xl");
    expect(skeletonDivs.length).toBeGreaterThanOrEqual(2);
  });
});
