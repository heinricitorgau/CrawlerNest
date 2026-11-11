import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import NavBar from "@/components/NavBar";

const refresh = jest.fn(async () => undefined);

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(""),
}));

jest.mock("@/hooks/useAuthPlaceholder", () => ({
  useAuth: () => ({ authenticated: true, currentUser: { id: 1, email: "someone@example.com" }, loading: false, refresh }),
}));

describe("NavBar sign out everywhere", () => {
  const fetchMock = jest.fn(async () => ({ ok: true, json: async () => ({}) }));

  beforeEach(() => {
    fetchMock.mockClear();
    refresh.mockClear();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it("asks first, then ends every token through the proxy route", async () => {
    jest.spyOn(window, "confirm").mockReturnValue(true);
    render(<NavBar />);
    fireEvent.click(screen.getByRole("button", { name: "Sign out everywhere" }));
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/signout-everywhere", expect.objectContaining({ method: "POST" }));
  });

  it("does nothing when the confirmation is declined", () => {
    jest.spyOn(window, "confirm").mockReturnValue(false);
    render(<NavBar />);
    fireEvent.click(screen.getByRole("button", { name: "Sign out everywhere" }));
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
