import { render, screen, within } from "@testing-library/react";
import { UsFederalData, formatFigure, statusText } from "@/components/UsFederalData";
import { CAVEAT_US_FEDERAL_PERIODS, CAVEAT_US_FEDERAL_SOURCE, CAVEAT_US_FEDERAL_SUPPRESSED } from "@/lib/caveatMessages";
import type { UsFederalMetric, UsInstitution } from "@/types/university";

function metric(key: string, overrides: Partial<UsFederalMetric> = {}): UsFederalMetric {
  return {
    source: "COLLEGE_SCORECARD", key, sourceField: key.toUpperCase(), unit: "count", value: 1, valueText: null,
    status: "reported", statusDetail: null, referencePeriod: "Fall 2024, reported in IPEDS DCY2024-25", release: "r",
    ...overrides,
  };
}

function institution(metrics: UsFederalMetric[], caveats = [CAVEAT_US_FEDERAL_SOURCE, CAVEAT_US_FEDERAL_PERIODS]): UsInstitution {
  return {
    canonicalUniversityId: 7, unitid: 166683, institutionName: "Massachusetts Institute of Technology", city: "Cambridge",
    stateCode: "MA", website: "web.mit.edu/", matchMethod: "wikidata_ipeds_id", wikidataId: "Q49108",
    sources: [
      { code: "COLLEGE_SCORECARD", name: "College Scorecard", publisher: "U.S. Department of Education",
        url: "https://collegescorecard.ed.gov/data/", license: "Public domain (U.S. federal government work)" },
      { code: "IPEDS", name: "IPEDS", publisher: "National Center for Education Statistics (NCES)",
        url: "https://nces.ed.gov/ipeds/", license: "Public domain (U.S. federal government work)" },
    ],
    metrics, caveats,
  };
}

function rowFor(label: string) {
  return screen.getByText(label).closest("div") as HTMLElement;
}

describe("formatting", () => {
  it("shows each unit as the source means it", () => {
    expect(formatFigure(metric("a", { unit: "ratio", value: 0.0455 }))).toBe("4.6%");
    expect(formatFigure(metric("a", { unit: "percent", value: 83 }))).toBe("83%");
    expect(formatFigure(metric("a", { unit: "usd", value: 85960 }))).toBe("$85,960");
    expect(formatFigure(metric("a", { unit: "count", value: 26904 }))).toBe("26,904");
    expect(formatFigure(metric("a", { unit: "code", value: 1, valueText: "Public" }))).toBe("Public");
  });

  it("never turns a missing figure into a number", () => {
    expect(statusText(metric("a", { status: "privacy_suppressed", value: null }))).toBe("Withheld by the source for privacy");
    expect(statusText(metric("a", { status: "not_available", value: null }))).toBe("Not available");
  });
});

describe("UsFederalData", () => {
  it("puts each value's own period beside it", () => {
    render(<UsFederalData data={institution([
      metric("admission_rate", { unit: "ratio", value: 0.0455 }),
      metric("median_earnings_10yr", { unit: "usd", value: 152553,
        referencePeriod: "Treasury AY2011-12, AY2012-13 pooled cohort measured in CY2022, CY2023" }),
    ])} />);
    expect(within(rowFor("Admission rate")).getByText(/Fall 2024, reported in IPEDS DCY2024-25/)).toBeInTheDocument();
    expect(within(rowFor("Median earnings 10 years after entry")).getByText(/Treasury AY2011-12/)).toBeInTheDocument();
    expect(within(rowFor("Median earnings 10 years after entry")).getByText("$152,553")).toBeInTheDocument();
  });

  it("says a withheld figure is withheld, and shows no zero for it", () => {
    render(<UsFederalData data={institution(
      [metric("median_debt_completers", { unit: "usd", value: null, status: "privacy_suppressed",
        statusDetail: "PS: privacy suppressed by the source" })],
      [CAVEAT_US_FEDERAL_SOURCE, CAVEAT_US_FEDERAL_PERIODS, CAVEAT_US_FEDERAL_SUPPRESSED],
    )} />);
    const row = rowFor("Median debt of completers");
    expect(within(row).getByText("Withheld by the source for privacy")).toBeInTheDocument();
    expect(row.textContent).not.toMatch(/\$0|\b0\b/);
    expect(screen.getByText(CAVEAT_US_FEDERAL_SUPPRESSED)).toBeInTheDocument();
  });

  it("marks an NCES estimate as one", () => {
    render(<UsFederalData data={institution([
      metric("applicants_total", { source: "IPEDS", value: 500, status: "imputed",
        statusDetail: "L: Imputed using the Group Median procedure", referencePeriod: "Admissions Data File, 2023-24" }),
    ])} />);
    const row = rowFor("Applicants");
    expect(within(row).getByText("NCES estimate")).toHaveAttribute("title", "L: Imputed using the Group Median procedure");
    expect(within(row).getByText(/IPEDS · Admissions Data File, 2023-24/)).toBeInTheDocument();
  });

  it("reads a 25th–75th pair as a range, and leaves out a row that does not apply", () => {
    render(<UsFederalData data={institution([
      metric("sat_math_25", { unit: "score", value: 780 }), metric("sat_math_75", { unit: "score", value: 800 }),
      metric("system_name", { source: "IPEDS", unit: "text", value: null, status: "not_applicable" }),
    ])} />);
    expect(within(rowFor("SAT math, 25th–75th percentile")).getByText("780–800")).toBeInTheDocument();
    expect(screen.queryByText("Part of")).not.toBeInTheDocument();
  });

  it("names the federal record and its sources, and renders the API's caveats verbatim", () => {
    render(<UsFederalData data={institution([metric("undergraduate_enrollment", { value: 4535 })])} />);
    expect(screen.getByText(/IPEDS UNITID 166683/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "College Scorecard" })).toHaveAttribute("href", "https://collegescorecard.ed.gov/data/");
    expect(screen.getByRole("link", { name: "IPEDS" })).toHaveAttribute("href", "https://nces.ed.gov/ipeds/");
    expect(screen.getByText(CAVEAT_US_FEDERAL_SOURCE)).toBeInTheDocument();
    expect(screen.getByText(CAVEAT_US_FEDERAL_PERIODS)).toBeInTheDocument();
  });
});
