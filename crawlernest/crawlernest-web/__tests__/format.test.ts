import { formatScore, formatRank, formatRankingScore, formatIelts } from "@/lib/format";

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
