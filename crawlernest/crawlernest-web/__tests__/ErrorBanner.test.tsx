import "@testing-library/jest-dom";
import { render, screen, fireEvent } from "@testing-library/react";
import ErrorBanner from "@/components/ErrorBanner";

describe("ErrorBanner", () => {
  it("renders the error message", () => {
    render(<ErrorBanner message="API request failed" onDismiss={() => {}} />);
    expect(screen.getByText("API request failed")).toBeInTheDocument();
  });

  it("renders a dismiss button", () => {
    render(<ErrorBanner message="Something went wrong" onDismiss={() => {}} />);
    expect(screen.getByRole("button", { name: /dismiss/i })).toBeInTheDocument();
  });

  it("calls onDismiss when dismiss button is clicked", () => {
    const onDismiss = jest.fn();
    render(<ErrorBanner message="Error!" onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("renders with role=alert for accessibility", () => {
    render(<ErrorBanner message="Network error" onDismiss={() => {}} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("displays a long error message without truncation", () => {
    const longMsg = "Unable to load rankings. Please check that the backend API server is running and accessible.";
    render(<ErrorBanner message={longMsg} onDismiss={() => {}} />);
    expect(screen.getByText(longMsg)).toBeInTheDocument();
  });

  it("does not call onDismiss until the button is clicked", () => {
    const onDismiss = jest.fn();
    render(<ErrorBanner message="Error" onDismiss={onDismiss} />);
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it("can be re-rendered with different messages", () => {
    const { rerender } = render(
      <ErrorBanner message="First error" onDismiss={() => {}} />
    );
    expect(screen.getByText("First error")).toBeInTheDocument();

    rerender(<ErrorBanner message="Second error" onDismiss={() => {}} />);
    expect(screen.getByText("Second error")).toBeInTheDocument();
    expect(screen.queryByText("First error")).not.toBeInTheDocument();
  });
});
