import { fireEvent, render, screen } from "@testing-library/react";
import CookieConsent from "@/components/CookieConsent";

beforeEach(() => localStorage.clear());

describe("CookieConsent", () => {
  it("shows until a choice is made, stores it, and stays hidden afterwards", () => {
    const { unmount } = render(<CookieConsent />);
    expect(screen.getByRole("dialog", { name: "Cookie consent" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /decline/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(localStorage.getItem("crawlernest_cookie_consent")).toBe("declined");
    unmount();
    render(<CookieConsent />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
