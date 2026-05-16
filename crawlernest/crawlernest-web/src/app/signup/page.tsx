import type { Metadata } from "next";
import AuthForm from "@/components/auth/AuthForm";

export const metadata: Metadata = {
  title: "Create Account | CrawlerNest",
  description: "Create a CrawlerNest account to explore global university intelligence.",
};

export default function SignUpPage() {
  return <AuthForm mode="signup" />;
}
