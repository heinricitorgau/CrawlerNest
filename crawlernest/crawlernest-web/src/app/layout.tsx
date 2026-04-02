import type { Metadata } from "next";
import NavBar from "@/components/NavBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "CrawlerNest — Global University Rankings",
  description: "Browse rankings of 2,736+ global universities. Aggregate data from QS and THE (Times Higher Education).",
  icons: {
    icon: "/icon.png",
    shortcut: "/icon.png",
    apple: "/icon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full font-sans">
        <NavBar />
        <div className="relative z-10">{children}</div>
        <div aria-hidden="true" className="site-watermark">
          <img
            src="/crawler-watermark.png"
            alt=""
            className="site-watermark-image"
          />
        </div>
      </body>
    </html>
  );
}
