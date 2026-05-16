"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useEffect, type FormEvent } from "react";
import type { AuthFieldError, AuthMode } from "@/types/auth";

interface AuthFormProps {
  mode: AuthMode;
}

type Phase = "idle" | "submitting" | "success";

function validate(email: string, password: string): AuthFieldError {
  const errors: AuthFieldError = {};
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.email = "Enter a valid email address.";
  }
  if (!password || password.length < 8) {
    errors.password = "Password must be at least 8 characters.";
  }
  return errors;
}

function extractErrorMessage(data: unknown): string | null {
  if (typeof data === "object" && data !== null && !Array.isArray(data)) {
    const d = data as Record<string, unknown>;
    if (typeof d.error === "string") return d.error;
    if (typeof d.message === "string") return d.message;
  }
  return null;
}

// ─── Checkmark icon ────────────────────────────────────────────────────────

function CheckIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
      stroke="#3d7a5a" strokeWidth="2.5" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

// ─── Success panels ────────────────────────────────────────────────────────

function SignupSuccessPanel({ email }: { email: string }) {
  return (
    <div className="text-center py-4">
      <div className="mx-auto mb-5 inline-flex h-12 w-12 items-center justify-center rounded-full bg-[#e8f2ec]">
        <CheckIcon />
      </div>
      <h2 className="text-xl font-bold text-[#1a3d2e]">Account created</h2>
      <p className="mt-2 text-sm text-[#6b7068]">
        Your CrawlerNest account for{" "}
        <span className="font-medium text-[#1a3d2e]">{email}</span> is ready.
      </p>
      <Link
        href="/signin"
        className="mt-6 inline-block w-full rounded-lg bg-[#1a3d2e] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
      >
        Sign in to continue →
      </Link>
      <p className="mt-4 text-center text-sm text-[#6b7068]">
        <Link href="/" className="underline-offset-4 hover:underline hover:text-[#1a3d2e]">
          ← Back to Rankings
        </Link>
      </p>
    </div>
  );
}

function SigninSuccessPanel({ email }: { email: string }) {
  return (
    <div className="text-center py-4">
      <div className="mx-auto mb-5 inline-flex h-12 w-12 items-center justify-center rounded-full bg-[#e8f2ec]">
        <CheckIcon />
      </div>
      <h2 className="text-xl font-bold text-[#1a3d2e]">Signed in</h2>
      <p className="mt-2 text-sm text-[#6b7068]">
        Welcome back,{" "}
        <span className="font-medium text-[#1a3d2e]">{email}</span>.
      </p>
      <p className="mt-3 text-xs text-[#6b7068]">Redirecting to rankings…</p>
    </div>
  );
}

// ─── Main form ─────────────────────────────────────────────────────────────

export default function AuthForm({ mode }: AuthFormProps) {
  const isSignIn = mode === "signin";
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState({ email: false, password: false });
  const [phase, setPhase] = useState<Phase>("idle");
  const [successEmail, setSuccessEmail] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const loading = phase === "submitting";

  const fieldErrors =
    submitted || touched.email || touched.password
      ? validate(email, password)
      : {};

  // After signin success, redirect to home after a brief moment.
  useEffect(() => {
    if (phase === "success" && isSignIn) {
      const tid = setTimeout(() => router.push("/"), 1500);
      return () => clearTimeout(tid);
    }
  }, [phase, isSignIn, router]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitted(true);
    setSubmitError(null);

    const errors = validate(email, password);
    if (errors.email || errors.password) return;

    setPhase("submitting");

    const normalizedEmail = email.trim().toLowerCase();
    const endpoint = isSignIn ? "/api/auth/signin" : "/api/auth/signup";

    let errorMsg: string | null = null;

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: normalizedEmail, password }),
      });

      let data: unknown = null;
      try {
        data = await res.json();
      } catch {
        /* non-JSON body */
      }

      if (res.ok) {
        setSuccessEmail(normalizedEmail);
        setPhase("success");
        return;
      }

      if (res.status === 409) {
        errorMsg = "An account with this email already exists.";
      } else if (res.status === 401) {
        errorMsg = "Invalid email or password.";
      } else if (res.status === 503) {
        errorMsg = "Authentication service is unavailable. Please try again later.";
      } else if (res.status === 400) {
        errorMsg =
          extractErrorMessage(data) ?? "Please check your input and try again.";
      } else {
        errorMsg = "Something went wrong. Please try again.";
      }
    } catch {
      errorMsg = "Could not connect to the server. Please check your connection.";
    }

    setSubmitError(errorMsg);
    setPhase("idle");
  }

  return (
    <div className="min-h-[calc(100vh-64px)] bg-[#f5f3ee] flex items-center justify-center px-4 py-16">
      <div className="w-full max-w-md">

        <div className="rounded-2xl border border-[#e0ddd8] bg-white px-8 py-10 shadow-sm">

          {phase === "success" ? (
            isSignIn ? (
              <SigninSuccessPanel email={successEmail} />
            ) : (
              <SignupSuccessPanel email={successEmail} />
            )
          ) : (
            <>
              {/* Header */}
              <div className="mb-8">
                <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-slate-900">
                  <span className="text-xs font-bold text-white">CN</span>
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-[#1a3d2e]">
                  {isSignIn ? "Sign in to CrawlerNest" : "Create an account"}
                </h1>
                <p className="mt-1.5 text-sm text-[#6b7068]">
                  {isSignIn
                    ? "Access your university research dashboard."
                    : "Start exploring global university intelligence."}
                </p>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} noValidate className="space-y-5">

                {/* Email */}
                <div>
                  <label
                    htmlFor="email"
                    className="block text-sm font-medium text-[#1a3d2e] mb-1.5"
                  >
                    Email address
                  </label>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onBlur={() => setTouched((t) => ({ ...t, email: true }))}
                    disabled={loading}
                    placeholder="you@example.com"
                    aria-describedby={fieldErrors.email ? "email-error" : undefined}
                    aria-invalid={!!fieldErrors.email}
                    className={`w-full rounded-lg border px-3 py-2.5 text-sm text-[#1a1a1a] placeholder-[#aaa] outline-none transition focus:ring-2 focus:ring-[#3d7a5a]/40 disabled:opacity-50 ${
                      fieldErrors.email
                        ? "border-red-400 bg-red-50"
                        : "border-[#e0ddd8] bg-white hover:border-[#b0ada8]"
                    }`}
                  />
                  {fieldErrors.email && (
                    <p id="email-error" className="mt-1.5 text-xs text-red-600">
                      {fieldErrors.email}
                    </p>
                  )}
                </div>

                {/* Password */}
                <div>
                  <label
                    htmlFor="password"
                    className="block text-sm font-medium text-[#1a3d2e] mb-1.5"
                  >
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    autoComplete={isSignIn ? "current-password" : "new-password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onBlur={() => setTouched((t) => ({ ...t, password: true }))}
                    disabled={loading}
                    placeholder={isSignIn ? "Your password" : "At least 8 characters"}
                    aria-describedby={
                      fieldErrors.password ? "password-error" : undefined
                    }
                    aria-invalid={!!fieldErrors.password}
                    className={`w-full rounded-lg border px-3 py-2.5 text-sm text-[#1a1a1a] placeholder-[#aaa] outline-none transition focus:ring-2 focus:ring-[#3d7a5a]/40 disabled:opacity-50 ${
                      fieldErrors.password
                        ? "border-red-400 bg-red-50"
                        : "border-[#e0ddd8] bg-white hover:border-[#b0ada8]"
                    }`}
                  />
                  {fieldErrors.password && (
                    <p id="password-error" className="mt-1.5 text-xs text-red-600">
                      {fieldErrors.password}
                    </p>
                  )}
                </div>

                {/* Submit error */}
                {submitError && (
                  <div
                    role="alert"
                    className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
                  >
                    {submitError}
                  </div>
                )}

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-lg bg-[#1a3d2e] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#2a5a42] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading
                    ? isSignIn
                      ? "Signing in…"
                      : "Creating account…"
                    : isSignIn
                    ? "Sign in"
                    : "Create account"}
                </button>
              </form>

              {/* Switch link */}
              <p className="mt-6 text-center text-sm text-[#6b7068]">
                {isSignIn ? "Don't have an account? " : "Already have an account? "}
                <Link
                  href={isSignIn ? "/signup" : "/signin"}
                  className="font-medium text-[#3d7a5a] underline-offset-4 hover:underline"
                >
                  {isSignIn ? "Create one" : "Sign in"}
                </Link>
              </p>
            </>
          )}
        </div>

        {phase !== "success" && (
          <p className="mt-6 text-center text-xs text-[#6b7068]">
            <Link
              href="/"
              className="underline-offset-4 hover:underline hover:text-[#1a3d2e]"
            >
              ← Back to Rankings
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
