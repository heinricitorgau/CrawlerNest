import type { MetadataRoute } from "next";
import { absoluteUrl } from "@/lib/site";

// Read CRAWLERNEST_SITE_URL per request: a build without it must not bake a
// robots.txt that never names the sitemap.
export const dynamic = "force-dynamic";

/** Account, personal and tool pages: nothing on them is public data worth indexing. */
const DISALLOWED_PATHS = [
  "/api/",
  "/signin",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/saved-universities",
  "/saved-recommendations",
  "/desk",
  "/admin",
  "/agent",
  "/preview",
  "/compare",
  "/recommendations",
  "/system-status",
  // Query-string variants (?year=, filters) duplicate the canonical page.
  "/*?",
] as const;

/** High-volume crawlers with no indexing value for this site. */
const BLOCKED_AGENTS = ["Bytespider", "PetalBot", "SemrushBot", "AhrefsBot", "MJ12bot", "DotBot"];

export default function robots(): MetadataRoute.Robots {
  const sitemap = absoluteUrl("/sitemap.xml");
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: [...DISALLOWED_PATHS], crawlDelay: 10 },
      ...BLOCKED_AGENTS.map((userAgent) => ({ userAgent, disallow: "/" })),
    ],
    ...(sitemap ? { sitemap } : {}),
  };
}
