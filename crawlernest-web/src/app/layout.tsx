import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CrawlerNest Website MVP",
  description: "CrawlerNest rankings and university detail explorer",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full font-sans">{children}</body>
    </html>
  );
}
