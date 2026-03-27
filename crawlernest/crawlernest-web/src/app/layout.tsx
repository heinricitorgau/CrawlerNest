import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CrawlerNest Website MVP",
  description: "CrawlerNest rankings and university detail explorer",
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
