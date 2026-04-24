import { render, screen } from "@testing-library/react";

import { AdmissionSignalBadge } from "@/components/AdmissionSignalBadge";


describe("AdmissionSignalBadge", () => {
  it("renders high confidence accepted signals", () => {
    render(
      <AdmissionSignalBadge
        label="IELTS"
        value={6.5}
        confidence={0.85}
        sourceCount={2}
        status="accepted"
      />
    );

    expect(screen.getByText("IELTS 6.5")).toBeInTheDocument();
    expect(screen.getByText("● High confidence")).toBeInTheDocument();
    expect(screen.getByText("2 sources")).toBeInTheDocument();
  });

  it("renders medium confidence accepted signals", () => {
    render(
      <AdmissionSignalBadge
        label="TOEFL"
        value={90}
        confidence={0.7}
        sourceCount={1}
        status="accepted"
      />
    );

    expect(screen.getByText("TOEFL 90")).toBeInTheDocument();
    expect(screen.getByText("● Medium confidence")).toBeInTheDocument();
    expect(screen.getByText("1 source")).toBeInTheDocument();
  });

  it("hides confidence for needs_review signals", () => {
    render(
      <AdmissionSignalBadge
        label="GPA"
        value={3.2}
        confidence={0.55}
        sourceCount={1}
        status="needs_review"
      />
    );

    expect(screen.getByText("GPA 3.2")).toBeInTheDocument();
    expect(screen.getByText("⚠ Needs review")).toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/source/i)).not.toBeInTheDocument();
  });

  it("shows conflict warning", () => {
    render(
      <AdmissionSignalBadge
        label="IELTS"
        value="6.0–6.5"
        confidence={0.8}
        sourceCount={2}
        status="conflict"
      />
    );

    expect(screen.getByText("IELTS 6.0–6.5")).toBeInTheDocument();
    expect(screen.getByText("⚠ Conflicting sources")).toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
  });

  it("shows source count only for accepted signals", () => {
    const { rerender } = render(
      <AdmissionSignalBadge
        label="IELTS"
        value={6.5}
        confidence={0.85}
        sourceCount={2}
        status="accepted"
      />
    );

    expect(screen.getByText("2 sources")).toBeInTheDocument();

    rerender(
      <AdmissionSignalBadge
        label="IELTS"
        value={6.5}
        confidence={0.85}
        sourceCount={2}
        status="conflict"
      />
    );

    expect(screen.queryByText("2 sources")).not.toBeInTheDocument();
  });
});
