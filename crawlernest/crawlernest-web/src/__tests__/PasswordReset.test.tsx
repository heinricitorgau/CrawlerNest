import { fireEvent, render, screen } from "@testing-library/react";
import AuthForm from "@/components/auth/AuthForm";
import { ForgotPasswordForm, ResetPasswordForm } from "@/components/auth/PasswordResetForms";

jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

const originalFetch = global.fetch;

function respond(status: number, body: unknown) {
  return { ok: status < 400, status, json: async () => body } as Response;
}

afterEach(() => {
  global.fetch = originalFetch;
});

describe("sign-in page", () => {
  it("links to forgot password, and sign-up does not", () => {
    const { unmount } = render(<AuthForm mode="signin" />);
    expect(screen.getByRole("link", { name: "Forgot password?" })).toHaveAttribute("href", "/forgot-password");
    unmount();
    render(<AuthForm mode="signup" />);
    expect(screen.queryByRole("link", { name: "Forgot password?" })).toBeNull();
  });
});

describe("ForgotPasswordForm", () => {
  it("sends the email and shows the API's own words", async () => {
    const fetchMock = jest.fn(async () => respond(200, {
      success: true,
      data: { message: "If an account exists for that email, a reset link has been written to the server log (development mode: no email is sent).", delivery: "log" },
    }));
    global.fetch = fetchMock as unknown as typeof fetch;
    render(<ForgotPasswordForm />);

    const send = screen.getByRole("button", { name: "Send reset link" });
    expect(send).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "  me@example.com " } });
    fireEvent.click(send);

    expect(await screen.findByRole("status")).toHaveTextContent("written to the server log");
    const [url, init] = (fetchMock.mock.calls as unknown as [string, RequestInit][])[0];
    expect(url).toBe("/api/auth/password-reset/request");
    expect(JSON.parse(String(init.body))).toEqual({ email: "me@example.com" });
  });
});

describe("ResetPasswordForm", () => {
  it("needs matching passwords of at least 8 characters before it sends", async () => {
    const fetchMock = jest.fn(async () => respond(200, { success: true, data: { message: "Your password has been changed. Sign in with the new one." } }));
    global.fetch = fetchMock as unknown as typeof fetch;
    render(<ResetPasswordForm token={"t".repeat(43)} />);
    const save = screen.getByRole("button", { name: "Set new password" });

    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "short" } });
    expect(screen.getByText("Password must be at least 8 characters.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "long-enough-1" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "long-enough-2" } });
    expect(screen.getByText("The two passwords do not match.")).toBeInTheDocument();
    expect(save).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "long-enough-1" } });
    fireEvent.click(save);
    expect(await screen.findByText("Password changed")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in →" })).toHaveAttribute("href", "/signin");
    const [, init] = (fetchMock.mock.calls as unknown as [string, RequestInit][])[0];
    expect(JSON.parse(String(init.body))).toEqual({ token: "t".repeat(43), newPassword: "long-enough-1" });
  });

  it("offers a new link when this one has expired", async () => {
    global.fetch = jest.fn(async () => respond(400, {
      success: false, error: "This reset link is invalid or has expired. Ask for a new one.",
    })) as unknown as typeof fetch;
    render(<ResetPasswordForm token={"t".repeat(43)} />);
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "long-enough-1" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "long-enough-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or has expired");
    expect(screen.getByRole("link", { name: "Ask for a new link" })).toHaveAttribute("href", "/forgot-password");
  });

  it("explains a link with no code instead of showing the form", () => {
    render(<ResetPasswordForm token={null} />);
    expect(screen.getByRole("alert")).toHaveTextContent("missing its code");
    expect(screen.queryByLabelText("New password")).toBeNull();
  });
});
