import { render, screen } from "@testing-library/react";

import AgentWarningBanner from "@/components/AgentWarningBanner";

/** Verbatim from crawlernest/agent/web_agent/policy/unsupported_year.py. */
const UNSUPPORTED_YEAR_WARNING =
  "UnsupportedYearWarning: Dataset is strictly locked to the 2026 snapshot. Year 2025 " +
  "is not available. This is not missing or incomplete data: the warehouse holds a " +
  "single-year 2026 snapshot and no rows for any other year, so any result shown here " +
  "describes 2026 rather than 2025.";

const PROVIDER_NOTE = "No web generation provider configured; deterministic fallback used.";

describe("AgentWarningBanner", () => {
  it("shows the unsupported-year disclosure in full", () => {
    render(<AgentWarningBanner warnings={[UNSUPPORTED_YEAR_WARNING]} />);

    const banner = screen.getByRole("alert");
    expect(banner).toBeInTheDocument();
    // The user has to be able to read that the answer describes 2026, not the
    // year they asked for, and that this is the snapshot's shape rather than a
    // lookup that came back empty.
    expect(banner).toHaveTextContent("Dataset is strictly locked to the 2026 snapshot");
    expect(banner).toHaveTextContent("Year 2025 is not available");
    expect(banner).toHaveTextContent("not missing or incomplete data");
  });

  it("labels the disclosure with a readable badge", () => {
    render(<AgentWarningBanner warnings={[UNSUPPORTED_YEAR_WARNING]} />);

    expect(screen.getByText("Unsupported year")).toBeInTheDocument();
    expect(
      screen.getByRole("alert").querySelector('[data-warning-code="UnsupportedYearWarning"]')
    ).not.toBeNull();
  });

  it("renders nothing for an ordinary response", () => {
    const { container } = render(<AgentWarningBanner warnings={[]} />);

    expect(screen.queryByRole("alert")).toBeNull();
    expect(container).toBeEmptyDOMElement();
  });

  it("does not surface generator notes to the reader", () => {
    // These fire on nearly every turn when no provider is configured. A banner
    // lit on every turn is one nobody reads, including the turn that matters.
    const { container } = render(<AgentWarningBanner warnings={[PROVIDER_NOTE]} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("shows every disclosure when a request names more than one bad year", () => {
    const second = UNSUPPORTED_YEAR_WARNING.replace(/2025/g, "2024");
    render(<AgentWarningBanner warnings={[UNSUPPORTED_YEAR_WARNING, second]} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Year 2025 is not available");
    expect(screen.getByRole("alert")).toHaveTextContent("Year 2024 is not available");
    expect(screen.getAllByText("Unsupported year")).toHaveLength(2);
  });

  it("lights up for the payload /api/agent/chat actually returns", () => {
    // The array the two-pass route builds: the engine's disclosure first, the
    // provider's own note after it. Asserted together because the banner is
    // only useful if it picks the first out of the second.
    render(
      <AgentWarningBanner
        warnings={[UNSUPPORTED_YEAR_WARNING, "Mock provider used. No external model was contacted."]}
      />
    );

    const banner = screen.getByRole("alert");
    expect(banner).toHaveTextContent("Unsupported year");
    expect(banner).toHaveTextContent("Year 2025 is not available");
    expect(banner).not.toHaveTextContent("Mock provider used");
  });

  it("renders nothing when the payload is malformed", () => {
    const { container } = render(<AgentWarningBanner warnings={undefined} />);

    expect(container).toBeEmptyDOMElement();
  });
});
