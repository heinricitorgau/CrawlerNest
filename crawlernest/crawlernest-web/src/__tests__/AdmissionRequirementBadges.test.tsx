import { render, screen } from "@testing-library/react";

import { AdmissionRequirementBadges } from "@/components/AdmissionRequirementBadges";

const NOTHING_PUBLISHED = {
  ieltsRequirement: null,
  toeflRequirement: null,
  duolingoRequirement: null,
  gpaRequirement: null,
  applicationDeadline: null,
};

/** A date `days` from now, as the ISO string the API sends. */
function isoDaysFromNow(days: number): string {
  const now = new Date();
  const utcMidnight = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return new Date(utcMidnight + days * 86_400_000).toISOString().slice(0, 10);
}

describe("AdmissionRequirementBadges", () => {
  it("renders a badge per published requirement", () => {
    render(
      <AdmissionRequirementBadges
        requirements={{
          ieltsRequirement: 6.5,
          toeflRequirement: 92,
          duolingoRequirement: 120,
          gpaRequirement: 3.5,
          applicationDeadline: null,
        }}
      />
    );

    expect(screen.getByText("6.5")).toBeInTheDocument();
    expect(screen.getByText("92")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("3.5")).toBeInTheDocument();
  });

  it("omits requirements the source did not publish rather than showing a placeholder", () => {
    render(
      <AdmissionRequirementBadges
        requirements={{ ...NOTHING_PUBLISHED, toeflRequirement: 90 }}
      />
    );

    expect(screen.getByText("TOEFL")).toBeInTheDocument();
    // A row of "Not available" pills would bury the one real number among them.
    expect(screen.queryByText("Not available")).not.toBeInTheDocument();
    expect(screen.queryByText("IELTS")).not.toBeInTheDocument();
    expect(screen.queryByText("GPA")).not.toBeInTheDocument();
    expect(screen.queryByText("Duolingo")).not.toBeInTheDocument();
  });

  it("never renders undefined or NaN when values are missing", () => {
    const { container } = render(
      <AdmissionRequirementBadges
        requirements={{
          ieltsRequirement: undefined,
          toeflRequirement: NaN,
          duolingoRequirement: null,
          gpaRequirement: undefined,
          applicationDeadline: undefined,
        }}
      />
    );

    expect(container.textContent).not.toMatch(/undefined|NaN/);
  });

  it("shows the empty message when nothing at all is published", () => {
    render(
      <AdmissionRequirementBadges
        requirements={NOTHING_PUBLISHED}
        emptyMessage="Nothing collected yet"
      />
    );

    expect(screen.getByText("Nothing collected yet")).toBeInTheDocument();
  });

  it("renders nothing at all when the empty message is suppressed", () => {
    const { container } = render(
      <AdmissionRequirementBadges requirements={NOTHING_PUBLISHED} emptyMessage={null} />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("formats a deadline without shifting it across a timezone boundary", () => {
    render(
      <AdmissionRequirementBadges
        requirements={{ ...NOTHING_PUBLISHED, applicationDeadline: "2099-01-01" }}
      />
    );

    // Parsed as local time this reads 31 Dec 2098 west of UTC, moving a deadline
    // a day earlier than the university published it.
    expect(screen.getByText("1 Jan 2099")).toBeInTheDocument();
  });

  it("marks a deadline that has already passed as closed", () => {
    render(
      <AdmissionRequirementBadges
        requirements={{ ...NOTHING_PUBLISHED, applicationDeadline: isoDaysFromNow(-5) }}
      />
    );

    expect(screen.getByText("closed")).toBeInTheDocument();
  });

  it("counts down a deadline that is still open", () => {
    render(
      <AdmissionRequirementBadges
        requirements={{ ...NOTHING_PUBLISHED, applicationDeadline: isoDaysFromNow(10) }}
      />
    );

    expect(screen.getByText("10d left")).toBeInTheDocument();
  });

  it("says today rather than 0d left on the closing day", () => {
    render(
      <AdmissionRequirementBadges
        requirements={{ ...NOTHING_PUBLISHED, applicationDeadline: isoDaysFromNow(0) }}
      />
    );

    expect(screen.getByText("today")).toBeInTheDocument();
  });

  it("ignores an unparseable deadline instead of rendering it raw", () => {
    render(
      <AdmissionRequirementBadges
        requirements={{ ...NOTHING_PUBLISHED, applicationDeadline: "not-a-date" }}
        emptyMessage="Nothing collected yet"
      />
    );

    expect(screen.queryByText("not-a-date")).not.toBeInTheDocument();
    expect(screen.getByText("Nothing collected yet")).toBeInTheDocument();
  });
});
