import { render, screen } from "@testing-library/react";
import { UsFederalFilterFields, UsFederalFilterSummary, isUsCountry, usFederalFilterParams } from "@/components/UsFederalFilter";
import { CAVEAT_US_FEDERAL_FILTER } from "@/lib/caveatMessages";

describe("US federal filter", () => {
  it("sends bounds only for the United States, with the rate as a fraction", () => {
    expect(isUsCountry(" United States ")).toBe(true);
    expect(isUsCountry("Puerto Rico")).toBe(true);
    expect(isUsCountry("United Kingdom")).toBe(false);
    expect(usFederalFilterParams("United States", { maxNetPrice: 25000, minAdmissionRatePercent: 20 }))
      .toEqual({ maxNetPrice: "25000", minAdmissionRate: "0.2" });
    expect(usFederalFilterParams("United Kingdom", { maxNetPrice: 25000, minAdmissionRatePercent: 20 })).toEqual({});
    expect(usFederalFilterParams("USA", { maxNetPrice: "", minAdmissionRatePercent: 150 })).toEqual({});
  });

  it("disables the fields outside the United States and says why", () => {
    render(<UsFederalFilterFields country="Japan" values={{ maxNetPrice: "", minAdmissionRatePercent: "" }} onChange={() => {}} />);
    expect(screen.getByText(/Available when the country is United States/)).toBeInTheDocument();
    for (const input of screen.getAllByRole("spinbutton")) expect(input).toBeDisabled();
  });

  it("reports the API's counts per reason and its caveats verbatim, and nothing when not applied", () => {
    const { container } = render(<UsFederalFilterSummary filter={{ applied: false }} />);
    expect(container).toBeEmptyDOMElement();

    render(
      <UsFederalFilterSummary
        filter={{
          applied: true,
          kept: 116,
          excluded: { no_federal_record: 3, figure_not_reported: 8, outside_range: 68 },
          reference_periods: { average_net_price: "AcadYr 2024-25" },
          caveats: [CAVEAT_US_FEDERAL_FILTER],
        }}
      />
    );
    expect(screen.getByText(/116 candidates kept/)).toHaveTextContent(
      "3 with no federal record here, 8 without a reported figure, 68 outside the range"
    );
    expect(screen.getByText(/average net price: AcadYr 2024-25/)).toBeInTheDocument();
    expect(screen.getByText(CAVEAT_US_FEDERAL_FILTER)).toBeInTheDocument();
  });
});
