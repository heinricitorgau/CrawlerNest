import type { Metadata } from "next";
import { ForgotPasswordForm } from "@/components/auth/PasswordResetForms";

export const metadata: Metadata = {
  title: "Reset Password | CrawlerNest",
  description: "Get a link to choose a new CrawlerNest password.",
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
