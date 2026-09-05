import {
  UNSUPPORTED_YEAR_WARNING_CODE,
  humanizeWarningCode,
  parseAgentWarning,
  selectDisclosureWarnings,
} from "@/lib/agentWarnings";

/** Verbatim from crawlernest/agent/web_agent/policy/unsupported_year.py. */
const UNSUPPORTED_YEAR_WARNING =
  "UnsupportedYearWarning: Dataset is strictly locked to the 2026 snapshot. Year 2025 " +
  "is not available. This is not missing or incomplete data: the warehouse holds a " +
  "single-year 2026 snapshot and no rows for any other year, so any result shown here " +
  "describes 2026 rather than 2025.";

/** The uncoded, generator-level notes the same array also carries. */
const PROVIDER_NOTE = "No web generation provider configured; deterministic fallback used.";

describe("parseAgentWarning", () => {
  it("splits a coded warning into code and disclosure", () => {
    const parsed = parseAgentWarning(UNSUPPORTED_YEAR_WARNING);

    expect(parsed.code).toBe(UNSUPPORTED_YEAR_WARNING_CODE);
    expect(parsed.raw).toBe(UNSUPPORTED_YEAR_WARNING);
    // The disclosure itself must survive byte-for-byte: only the machine code
    // prefix is removed. Rewording it here would open a fifth copy of a string
    // the backend contract test already guards.
    expect(parsed.message).toBe(
      UNSUPPORTED_YEAR_WARNING.slice(`${UNSUPPORTED_YEAR_WARNING_CODE}: `.length)
    );
    expect(parsed.message.startsWith("Dataset is strictly locked")).toBe(true);
  });

  it("leaves an uncoded warning whole", () => {
    const parsed = parseAgentWarning(PROVIDER_NOTE);

    expect(parsed.code).toBeNull();
    expect(parsed.message).toBe(PROVIDER_NOTE);
  });

  it("does not treat a colon mid-sentence as a code", () => {
    const parsed = parseAgentWarning("Note: two sources disagreed");

    expect(parsed.code).toBeNull();
  });
});

describe("selectDisclosureWarnings", () => {
  it("keeps coded disclosures and drops generator notes", () => {
    const selected = selectDisclosureWarnings([PROVIDER_NOTE, UNSUPPORTED_YEAR_WARNING]);

    expect(selected).toHaveLength(1);
    expect(selected[0].code).toBe(UNSUPPORTED_YEAR_WARNING_CODE);
  });

  it("preserves backend order across several disclosures", () => {
    const second = UNSUPPORTED_YEAR_WARNING.replace(/2025/g, "2024");
    const selected = selectDisclosureWarnings([UNSUPPORTED_YEAR_WARNING, second]);

    expect(selected.map((warning) => warning.raw)).toEqual([
      UNSUPPORTED_YEAR_WARNING,
      second,
    ]);
  });

  it("returns nothing for the ordinary response", () => {
    expect(selectDisclosureWarnings([])).toEqual([]);
    expect(selectDisclosureWarnings([PROVIDER_NOTE])).toEqual([]);
  });

  it("survives a malformed payload", () => {
    // This reads JSON off the wire. A bad shape must not throw and take the
    // whole answer down with it.
    expect(selectDisclosureWarnings(undefined)).toEqual([]);
    expect(selectDisclosureWarnings(null)).toEqual([]);
    expect(selectDisclosureWarnings("not an array")).toEqual([]);
    expect(selectDisclosureWarnings([null, 42, "", "   "])).toEqual([]);
  });
});

describe("humanizeWarningCode", () => {
  it("turns a code into a readable badge label", () => {
    expect(humanizeWarningCode(UNSUPPORTED_YEAR_WARNING_CODE)).toBe("Unsupported year");
    expect(humanizeWarningCode("StaleDataWarning")).toBe("Stale data");
  });

  it("falls back rather than rendering an empty badge", () => {
    expect(humanizeWarningCode("Warning")).toBe("Warning");
  });
});
