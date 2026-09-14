import { ENTITY_CHANGED_LABEL, presentRankDelta, RANK_DELTA_REASON_TEXT } from "@/lib/rankDeltaPresentation";
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

  it("shows a banded move as both printed bands when both are known", () => {
    const up = presentRankDelta({
      rankDelta: delta({ min: -59, max: -41, direction: "up", priorRankDisplay: "601–610" }),
      rankDeltaReason: "banded",
      rankDisplay: "551–560",
    });
    expect(up.label).toBe("↑ 601–610 → 551–560");
    expect(up.detail).toBe("Up between 41 and 59 places since 2025 (601–610 → 551–560); the source publishes a band, not an exact rank.");
    expect(up.label).not.toMatch(/\b(41|59)\b/);

    const down = presentRankDelta({
      rankDelta: delta({ min: 1, max: null, direction: "down", priorRankDisplay: "1401–1500" }),
      rankDeltaReason: "banded",
      rankDisplay: "1501+",
    });
    expect(down.label).toBe("↓ 1401–1500 → 1501+");
  });

  it("never assembles an interval from one printed rank", () => {
    const shown = presentRankDelta({
      rankDelta: delta({ min: -59, max: -41, direction: "up", priorRankDisplay: "601–610" }),
      rankDeltaReason: "banded",
      rankDisplay: null,
    });
    expect(shown.label).toBe("↑ banded since 2025");
  });

  it("claims no direction when overlapping bands leave it unknown", () => {
    const shown = presentRankDelta({ rankDelta: delta({ min: -99, max: 99, direction: "indeterminate" }), rankDeltaReason: "banded" });
    expect(shown.tone).toBe("neutral");
    expect(shown.label).not.toMatch(/[↑↓]/);
    const printed = presentRankDelta({
      rankDelta: delta({ min: -9, max: 9, direction: "indeterminate", priorRankDisplay: "201–250" }),
      rankDeltaReason: "banded",
      rankDisplay: "201–250",
    });
    expect(printed).toMatchObject({ label: "201–250 → 201–250", tone: "neutral" });
  });

  it("shows no movement and explains a withheld one", () => {
    for (const reason of ["single_year_dataset", "composite_rank_not_comparable", "no_prior_row", "suspicious_merge", "rank_display_missing"]) {
      const shown = presentRankDelta({ rankDelta: null, rankDeltaReason: reason });
      expect(shown).toEqual({ label: "—", detail: RANK_DELTA_REASON_TEXT[reason], tone: "withheld" });
    }
  });

  it("marks a changed entity distinctly, not as missing data", () => {
    const shown = presentRankDelta({ rankDelta: null, rankDeltaReason: "entity_changed" });
    expect(shown).toEqual({ label: ENTITY_CHANGED_LABEL, detail: RANK_DELTA_REASON_TEXT.entity_changed, tone: "entity_changed" });
    // The code also covers a split, a rename and a source re-key; "merged" would overclaim.
    expect(shown.label).not.toMatch(/merg/i);
    expect(shown.detail).toMatch(/merger, split or rename/);
  });

  it("believes entity_changed over any movement sent with it", () => {
    for (const rankDelta of [delta({ value: -5 }), delta({ value: -5, min: -5, max: -5, direction: "up" })]) {
      const shown = presentRankDelta({ rankDelta, rankDeltaReason: "entity_changed" });
      expect(shown.tone).toBe("entity_changed");
      expect(shown.label).not.toMatch(/[↑↓]|\d/);
    }
  });

  it("does not trust a delta the API sent without a direction", () => {
    const shown = presentRankDelta({ rankDelta: delta({ value: -5 }), rankDeltaReason: null });
    expect(shown.tone).toBe("withheld");
    expect(shown.label).toBe("—");
  });

  it("renders a reason code it does not know as withheld", () => {
    expect(presentRankDelta({ rankDelta: null, rankDeltaReason: "some_future_reason" }))
      .toEqual({ label: "—", detail: "No rank change is available for this source.", tone: "withheld" });
  });

  it("never uses verdict words", () => {
    const rows = [
      presentRankDelta({ rankDelta: delta({ value: -3, min: -3, max: -3, direction: "up" }), rankDeltaReason: null }),
      presentRankDelta({ rankDelta: delta({ value: 3, min: 3, max: 3, direction: "down" }), rankDeltaReason: null }),
    ];
    for (const row of rows) expect(`${row.label} ${row.detail}`).not.toMatch(/improv|declin|better|worse/i);
  });
});
