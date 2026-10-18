import type { Metadata } from "next";
import { ResetPasswordForm } from "@/components/auth/PasswordResetForms";

export const metadata: Metadata = {
  title: "Choose a New Password | CrawlerNest",
  description: "Set a new CrawlerNest password with your reset link.",
  // The URL carries a one-time token: keep it out of referrers and search engines.
  referrer: "no-referrer",
  robots: { index: false, follow: false },
};

export default async function ResetPasswordPage({ searchParams }: { searchParams: Promise<{ token?: string | string[] }> }) {
  const { token } = await searchParams;
  return <ResetPasswordForm token={typeof token === "string" && token ? token : null} />;
}
