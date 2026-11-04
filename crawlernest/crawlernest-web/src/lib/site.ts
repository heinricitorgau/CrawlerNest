/**
 * The site's public origin, for absolute URLs in metadata, robots.txt and sitemap.xml.
 *
 * Read from `CRAWLERNEST_SITE_URL` (for example `https://crawlernest.example`). Unset,
 * or not an http(s) URL, it is null, and everything built on it is left out rather than
 * pointed at localhost: no canonical links, no Open Graph URLs, no sitemap entries, no
 * `Sitemap:` line. A search engine that is handed a localhost URL indexes nothing useful.
 *
 * Statically prerendered pages read it at build time and robots/sitemap at request time,
 * so a deployment sets it in both places (deploy/docker-compose.yml does).
 */
export function getSiteUrl(raw: string | undefined = process.env.CRAWLERNEST_SITE_URL): URL | null {
  const value = raw?.trim();
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    // An origin plus an optional base path. (An http URL's path is never empty, so the
    // trailing slash is dropped where paths are joined, in absoluteUrl.)
    url.search = "";
    url.hash = "";
    return url;
  } catch {
    return null;
  }
}

/** An absolute URL for a site path, or null when the site URL is not configured. */
export function absoluteUrl(path: string, site: URL | null = getSiteUrl()): string | null {
  if (!site) return null;
  const base = site.pathname.replace(/\/+$/, "");
  return `${site.origin}${base}${path.startsWith("/") ? path : `/${path}`}`;
}

/** The path of a university page. Slugs can hold non-ASCII letters and apostrophes. */
export function universityPath(slug: string): string {
  return `/universities/${encodeURIComponent(slug)}`;
}
