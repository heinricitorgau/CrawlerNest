import {
  formatScore,
  formatRank,
  formatRankingScore,
  formatIelts,
  formatToefl,
  formatDuolingo,
  formatGpa,
  formatDeadline,
  formatDegreeLevel,
} from "@/lib/format";

describe("formatScore", () => {
  it("formats a regular score to 1 decimal place", () => {
    expect(formatScore(85.678)).toBe("85.7");
  });

  it("formats zero", () => {
    expect(formatScore(0)).toBe("0.0");
  });

  it("returns 'Not available' for null", () => {
    expect(formatScore(null)).toBe("Not available");
  });

  it("returns 'Not available' for undefined", () => {
    expect(formatScore(undefined)).toBe("Not available");
  });

  it("returns 'Not available' for NaN", () => {
    expect(formatScore(NaN)).toBe("Not available");
  });

  it("formats a score that is already 1 decimal", () => {
    expect(formatScore(72.5)).toBe("72.5");
  });
});

describe("formatRank", () => {
  it("formats a rank as a localized integer", () => {
    expect(formatRank(42)).toBe("42");
  });

  it("rounds a float rank", () => {
    expect(formatRank(42.7)).toBe("43");
  });

  it("returns 'Not available' for null", () => {
    expect(formatRank(null)).toBe("Not available");
  });

  it("returns 'Not available' for undefined", () => {
    expect(formatRank(undefined)).toBe("Not available");
  });

  it("returns 'Not available' for NaN", () => {
    expect(formatRank(NaN)).toBe("Not available");
  });

  it("formats rank 1", () => {
    expect(formatRank(1)).toBe("1");
  });
});

describe("formatRankingScore", () => {
  it("rounds and localizes a score", () => {
    expect(formatRankingScore(95.4)).toBe("95");
  });

  it("returns 'Not available' for null", () => {
    expect(formatRankingScore(null)).toBe("Not available");
  });

  it("returns 'Not available' for undefined", () => {
    expect(formatRankingScore(undefined)).toBe("Not available");
  });

  it("returns 'Not available' for NaN", () => {
    expect(formatRankingScore(NaN)).toBe("Not available");
  });
});

describe("formatIelts", () => {
  it("formats an IELTS score to 1 decimal", () => {
    expect(formatIelts(6.5)).toBe("6.5");
  });

  it("formats 7.0 correctly", () => {
    expect(formatIelts(7)).toBe("7.0");
  });

  it("returns 'Not available' for null", () => {
    expect(formatIelts(null)).toBe("Not available");
  });

  it("returns 'Not available' for undefined", () => {
    expect(formatIelts(undefined)).toBe("Not available");
  });

  it("returns 'Not available' for NaN", () => {
    expect(formatIelts(NaN)).toBe("Not available");
  });
});

describe("formatToefl", () => {
  it("formats a TOEFL score as a whole number", () => {
    expect(formatToefl(92)).toBe("92");
  });

  it.each([null, undefined, NaN])("returns 'Not available' for %p", (value) => {
    expect(formatToefl(value as number | null | undefined)).toBe("Not available");
  });
});

describe("formatDuolingo", () => {
  it("formats a Duolingo score as a whole number", () => {
    expect(formatDuolingo(120)).toBe("120");
  });

  it.each([null, undefined, NaN])("returns 'Not available' for %p", (value) => {
    expect(formatDuolingo(value as number | null | undefined)).toBe("Not available");
  });
});

describe("formatGpa", () => {
  it("keeps a one-decimal GPA as written", () => {
    expect(formatGpa(3.5)).toBe("3.5");
  });

  it("keeps two decimals when the source published them", () => {
    expect(formatGpa(3.45)).toBe("3.45");
  });

  it("does not invent trailing precision for a whole number", () => {
    expect(formatGpa(4)).toBe("4");
  });

  it.each([null, undefined, NaN])("returns 'Not available' for %p", (value) => {
    expect(formatGpa(value as number | null | undefined)).toBe("Not available");
  });
});

describe("formatDeadline", () => {
  it("formats an ISO date", () => {
    expect(formatDeadline("2026-01-15")).toBe("15 Jan 2026");
  });

  it("does not shift the date into the viewer's timezone", () => {
    // Parsed as local time this would render 31 Dec 2025 anywhere west of UTC,
    // moving the deadline a day earlier than the university published it.
    expect(formatDeadline("2026-01-01")).toBe("1 Jan 2026");
  });

  it.each([null, undefined, "", "not-a-date"])(
    "returns 'Not available' for %p",
    (value) => {
      expect(formatDeadline(value as string | null | undefined)).toBe("Not available");
    }
  );
});

describe("formatDegreeLevel", () => {
  it("capitalises a degree level", () => {
    expect(formatDegreeLevel("postgraduate")).toBe("Postgraduate");
  });

  it("falls back to 'All levels' when the entry spans every level", () => {
    expect(formatDegreeLevel(null)).toBe("All levels");
    expect(formatDegreeLevel("")).toBe("All levels");
  });
});
