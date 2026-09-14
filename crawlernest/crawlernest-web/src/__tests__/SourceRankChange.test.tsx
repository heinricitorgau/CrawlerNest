import { render, screen } from "@testing-library/react";

import { SourceRankChange, anyEntityChanged, anyRankChangeShown } from "@/components/SourceRankChange";
import type { RankDelta, UniversityRanking } from "@/types/university";

const delta = (overrides: Partial<RankDelta>): RankDelta => ({
  priorYear: 2025,
  currentYear: 2026,
  priorRankDisplay: null,
  value: null,
  min: null,
  max: null,
  direction: null,
  ...overrides,
});

const row = (overrides: Partial<UniversityRanking>): UniversityRanking => ({
  source: "QS",
  year: 2026,
  rank: 40,
  rankDisplay: "40",
  score: 80,
  rankDelta: null,
  rankDeltaReason: null,
  ...overrides,
});

describe("SourceRankChange", () => {
  it("shows an exact move with its full sentence for assistive technology", () => {
    const { container } = render(
      <SourceRankChange ranking={row({ rankDelta: delta({ value: -3, min: -3, max: -3, direction: "up", priorRankDisplay: "43" }) })} />,
    );
    const cell = container.querySelector("[data-tone]")!;
    expect(cell).toHaveAttribute("data-tone", "up");
    expect(cell).toHaveAttribute("title", "Up 3 places since 2025 (was 43).");
    expect(screen.getByText("↑ 3 since 2025")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText(/QS: ↑ 3 since 2025\. Up 3 places since 2025/)).toHaveClass("sr-only");
  });

  it("shows a banded move as the printed bands", () => {
    render(
      <SourceRankChange
        ranking={row({
          source: "THE",
          rankDisplay: "551–560",
          rankDelta: delta({ min: -59, max: -41, direction: "up", priorRankDisplay: "601–610" }),
          rankDeltaReason: "banded",
        })}
      />,
    );
    expect(screen.getByText("↑ 601–610 → 551–560")).toBeInTheDocument();
  });

  it("styles a changed entity as its own badge, with no number", () => {
    const { container } = render(<SourceRankChange ranking={row({ rankDeltaReason: "entity_changed" })} />);
    const cell = container.querySelector("[data-tone]")!;
    expect(cell).toHaveAttribute("data-tone", "entity_changed");
    expect(cell.className).toMatch(/border-dashed/);
    expect(screen.getByText("Entity changed")).toBeInTheDocument();
    expect(cell.textContent).not.toMatch(/[↑↓]/);
  });

  it("keeps a withheld change quiet", () => {
    const { container } = render(<SourceRankChange ranking={row({ rankDeltaReason: "no_prior_row" })} />);
    expect(container.querySelector("[data-tone]")).toHaveAttribute("data-tone", "withheld");
    expect(screen.getByText(/QS: no rank change shown\./)).toHaveClass("sr-only");
  });
});

describe("when the rank-change caveat applies", () => {
  it("applies to a shown movement or a changed entity, not to withheld gaps", () => {
    const moved = row({ rankDelta: delta({ value: 1, min: 1, max: 1, direction: "down" }) });
    const merged = row({ rankDeltaReason: "entity_changed" });
    const gap = row({ rankDeltaReason: "no_prior_row" });

    expect(anyRankChangeShown([gap, moved])).toBe(true);
    expect(anyRankChangeShown([gap, merged])).toBe(false);
    expect(anyEntityChanged([gap, merged])).toBe(true);
    expect(anyRankChangeShown([gap]) || anyEntityChanged([gap])).toBe(false);
  });
});
