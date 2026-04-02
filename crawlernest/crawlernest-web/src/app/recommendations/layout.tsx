import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "My Recommendations | CrawlerNest",
  description: "Generate personalized university recommendations based on your ranking targets, IELTS score, and risk profile.",
};

export default function RecommendationsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
