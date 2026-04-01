import { formatScore, formatRank, formatRankingScore, formatIelts } from "@/lib/format";

describe("formatScore", () => {
  it("returns one decimal place for a valid score", () => {
    expect(formatScore(95.6789)).toBe("95.7");
  });

  it("returns '0.0' for zero", () => {
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

  it("formats whole number with .0", () => {
    expect(formatScore(100)).toBe("100.0");
  });
});

describe("formatRank", () => {
  it("returns integer string for a whole rank", () => {
    expect(formatRank(1)).toBe("1");
  });

  it("rounds a float rank", () => {
    expect(formatRank(4.6)).toBe("5");
  });

  it("uses locale formatting for large numbers", () => {
    const result = formatRank(1500);
    expect(result).toMatch(/1[,.]?500/);
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
});

describe("formatRankingScore", () => {
  it("rounds and formats an integer", () => {
    expect(formatRankingScore(87.9)).toMatch(/88/);
  });

  it("returns 'Not available' for null", () => {
    expect(formatRankingScore(null)).toBe("Not available");
  });

  it("returns 'Not available' for undefined", () => {
    expect(formatRankingScore(undefined)).toBe("Not available");
  });

  it("handles zero", () => {
    expect(formatRankingScore(0)).toMatch(/0/);
  });
});

describe("formatIelts", () => {
  it("formats IELTS score to one decimal", () => {
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
