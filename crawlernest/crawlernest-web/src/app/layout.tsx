import type { Metadata } from "next";
import type { ReactNode } from "react";
import NavBar from "@/components/NavBar";
import CookieConsent from "@/components/CookieConsent";
import { siteDescription } from "@/lib/seo";
import { getSiteUrl } from "@/lib/site";
import "./globals.css";

const siteUrl = getSiteUrl();

export const metadata: Metadata = {
  // Only with a configured public URL: relative metadata URLs need it, and a
  // localhost base would hand crawlers links to nowhere.
  ...(siteUrl ? { metadataBase: siteUrl } : {}),
  title: "CrawlerNest — Global University Rankings",
  description: siteDescription(),
  openGraph: { type: "website", siteName: "CrawlerNest", title: "CrawlerNest — Global University Rankings", description: siteDescription() },
  icons: {
    icon: "/icon.png",
    shortcut: "/icon.png",
    apple: "/icon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full">
        <NavBar />
        <div className="relative">{children}</div>
        <CookieConsent />
      </body>
    </html>
  );
}
