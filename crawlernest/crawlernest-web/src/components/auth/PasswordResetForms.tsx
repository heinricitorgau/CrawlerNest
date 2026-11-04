"use client";

import Link from "next/link";
import { useState, type FormEvent, type ReactNode } from "react";
import { AUTH_MESSAGES } from "@/lib/authMessages";

/**
 * "Forgot password": ask for a link, then set a new password with it.
 *
 * The request form shows whatever the API answers. The API words it the same for
 * every email (so the form cannot reveal who has an account) and truthfully about
 * where the link went -- in development it is the server log, not an inbox.
 */

const MIN_PASSWORD = 8;
const input =
  "w-full rounded-lg border border-(--color-rule) bg-white px-3 py-2.5 text-sm text-(--color-ink) placeholder-(--color-muted) outline-none transition hover:border-(--color-muted) focus:ring-2 focus:ring-(--color-ink-2)/40 disabled:opacity-50";
const button =
  "w-full rounded-lg bg-(--color-ink) px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-(--color-ink-2) disabled:cursor-not-allowed disabled:opacity-60";

function Card({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return (
    <div className="min-h-[calc(100vh-64px)] bg-(--color-paper) flex items-center justify-center px-4 py-16">
      <div className="w-full max-w-md">
        <div className="rounded-2xl border border-(--color-rule) bg-white px-8 py-10 shadow-sm">
          <div className="mb-8">
            <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-slate-900">
              <span className="text-xs font-bold text-white">CN</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-(--color-ink)">{title}</h1>
            <p className="mt-1.5 text-sm text-(--color-muted)">{intro}</p>
          </div>
          {children}
        </div>
        <p className="mt-6 text-center text-xs text-(--color-muted)">
          <Link href="/signin" className="underline-offset-4 hover:underline hover:text-(--color-ink)">← Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}

async function post(path: string, body: unknown): Promise<{ ok: boolean; message: string }> {
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = (await res.json().catch(() => null)) as { data?: { message?: string }; error?: string } | null;
    if (res.ok) return { ok: true, message: data?.data?.message ?? "Done." };
    return { ok: false, message: data?.error ?? AUTH_MESSAGES.backendUnavailable };
  } catch {
    return { ok: false, message: AUTH_MESSAGES.networkError };
  }
}

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || sending) return;
    setSending(true);
    setResult(await post("/api/auth/password-reset/request", { email: email.trim() }));
    setSending(false);
  }

  return (
    <Card title="Reset your password" intro="Enter the email you signed up with, and we'll send a link to choose a new password.">
      {result?.ok ? (
        <div role="status" className="rounded-lg border border-(--color-rule) bg-(--color-paper) px-4 py-3 text-sm text-(--color-ink)">
          {result.message}
        </div>
      ) : (
        <form onSubmit={submit} noValidate className="space-y-5">
          <div>
            <label htmlFor="reset-email" className="mb-1.5 block text-sm font-medium text-(--color-ink)">Email address</label>
            <input id="reset-email" type="email" autoComplete="email" value={email} disabled={sending}
              onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" className={input} />
          </div>
          {result ? <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{result.message}</div> : null}
          <button type="submit" disabled={!valid || sending} className={button}>{sending ? "Sending…" : "Send reset link"}</button>
        </form>
      )}
    </Card>
  );
}

export function ResetPasswordForm({ token }: { token: string | null }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;
  const mismatch = confirm.length > 0 && confirm !== password;
  const valid = password.length >= MIN_PASSWORD && confirm === password;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || saving || !token) return;
    setSaving(true);
    setResult(await post("/api/auth/password-reset/confirm", { token, newPassword: password }));
    setSaving(false);
  }

  if (!token) {
    return (
      <Card title="Reset your password" intro="This page needs the link from your reset email.">
        <p role="alert" className="text-sm text-amber-800">The link is missing its code. Open the full link, or ask for a new one.</p>
        <Link href="/forgot-password" className={`${button} mt-5 block text-center`}>Ask for a new link</Link>
      </Card>
    );
  }

  if (result?.ok) {
    return (
      <Card title="Password changed" intro="You can sign in with your new password now.">
        <p role="status" className="text-sm text-(--color-ink)">{result.message}</p>
        <Link href="/signin" className={`${button} mt-5 block text-center`}>Sign in →</Link>
      </Card>
    );
  }

  return (
    <Card title="Choose a new password" intro="At least 8 characters. The link works once.">
      <form onSubmit={submit} noValidate className="space-y-5">
        <div>
          <label htmlFor="new-password" className="mb-1.5 block text-sm font-medium text-(--color-ink)">New password</label>
          <input id="new-password" type="password" autoComplete="new-password" value={password} disabled={saving}
            onChange={(e) => setPassword(e.target.value)} className={input} />
          {tooShort ? <p className="mt-1.5 text-xs text-red-600">Password must be at least {MIN_PASSWORD} characters.</p> : null}
        </div>
        <div>
          <label htmlFor="confirm-password" className="mb-1.5 block text-sm font-medium text-(--color-ink)">Confirm new password</label>
          <input id="confirm-password" type="password" autoComplete="new-password" value={confirm} disabled={saving}
            onChange={(e) => setConfirm(e.target.value)} className={input} />
          {mismatch ? <p className="mt-1.5 text-xs text-red-600">The two passwords do not match.</p> : null}
        </div>
        {result ? (
          <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {result.message}{" "}
            <Link href="/forgot-password" className="font-medium underline">Ask for a new link</Link>
          </div>
        ) : null}
        <button type="submit" disabled={!valid || saving} className={button}>{saving ? "Saving…" : "Set new password"}</button>
      </form>
    </Card>
  );
}
