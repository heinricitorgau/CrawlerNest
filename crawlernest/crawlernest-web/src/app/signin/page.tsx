import type { Metadata } from "next";
import AuthForm from "@/components/auth/AuthForm";

export const metadata: Metadata = {
  title: "Sign In | CrawlerNest",
  description: "Sign in to your CrawlerNest account.",
};

export default function SignInPage() {
  return <AuthForm mode="signin" />;
}
