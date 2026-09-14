import { presentRankDelta, RANK_DELTA_REASON_TEXT } from "@/lib/rankDeltaPresentation";
import type { RankDelta } from "@/types/university";

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

describe("presentRankDelta", () => {
  it("states an exact move up in the API's direction, not the sign", () => {
    const shown = presentRankDelta({ rankDelta: delta({ value: -3, min: -3, max: -3, direction: "up", priorRankDisplay: "17" }), rankDeltaReason: null });
    expect(shown).toEqual({ label: "↑ 3 since 2025", detail: "Up 3 places since 2025 (was 17).", tone: "up" });
  });

  it("states an exact move down and an unchanged rank", () => {
    expect(presentRankDelta({ rankDelta: delta({ value: 1, min: 1, max: 1, direction: "down" }), rankDeltaReason: null }))
      .toMatchObject({ label: "↓ 1 since 2025", detail: "Down 1 place since 2025.", tone: "down" });
    expect(presentRankDelta({ rankDelta: delta({ value: 0, min: 0, max: 0, direction: "unchanged" }), rankDeltaReason: null }))
      .toMatchObject({ label: "No change since 2025", tone: "neutral" });
  });

  it("gives a banded move as a range, never a number of places", () => {
    const up = presentRankDelta({ rankDelta: delta({ min: -149, max: -51, direction: "up" }), rankDeltaReason: "banded" });
    expect(up.label).toBe("↑ banded since 2025");
    expect(up.detail).toContain("between 51 and 149 places");
    const open = presentRankDelta({ rankDelta: delta({ min: 1, max: null, direction: "down" }), rankDeltaReason: "banded" });
    expect(open.detail).toContain("at least 1 place");
  });

  it("claims no direction when overlapping bands leave it unknown", () => {
    const shown = presentRankDelta({ rankDelta: delta({ min: -99, max: 99, direction: "indeterminate" }), rankDeltaReason: "banded" });
    expect(shown.tone).toBe("neutral");
    expect(shown.label).not.toMatch(/[↑↓]/);
  });

  it("shows no movement and explains a withheld one", () => {
    for (const reason of ["single_year_dataset", "entity_changed", "composite_rank_not_comparable", "no_prior_row"]) {
      const shown = presentRankDelta({ rankDelta: null, rankDeltaReason: reason });
      expect(shown).toEqual({ label: "—", detail: RANK_DELTA_REASON_TEXT[reason], tone: "withheld" });
    }
  });

  it("does not trust a delta the API sent without a direction", () => {
    const shown = presentRankDelta({ rankDelta: delta({ value: -5 }), rankDeltaReason: "entity_changed" });
    expect(shown.tone).toBe("withheld");
    expect(shown.label).toBe("—");
  });

  it("never uses verdict words", () => {
    const rows = [
      presentRankDelta({ rankDelta: delta({ value: -3, min: -3, max: -3, direction: "up" }), rankDeltaReason: null }),
      presentRankDelta({ rankDelta: delta({ value: 3, min: 3, max: 3, direction: "down" }), rankDeltaReason: null }),
    ];
    for (const row of rows) expect(`${row.label} ${row.detail}`).not.toMatch(/improv|declin|better|worse/i);
  });
});
