"use client";

import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuthPlaceholder";
import { YearSelector, YearSelectorFallback } from "@/components/YearSelector";
import { YEAR_QUERY_PARAM, hrefForEdition, resolveSelectedYear } from "@/lib/datasetScope";

/**
 * Pages whose data depends on the selected edition. The nav offers the edition
 * selector only here -- on /about it would change nothing -- and links into these
 * pages carry the current `?year=` so moving between them keeps the edition.
 */
export const YEAR_AWARE_PATHS: readonly string[] = [
  "/",
  "/rankings",
  "/recommendations",
  "/compare",
  "/subject-rankings",
];

/** A university's own page; its sources sub-page is not scoped to an edition. */
const UNIVERSITY_DETAIL_PATH = /^\/universities\/[^/]+\/?$/;

export function isYearAwarePath(pathname: string): boolean {
  return YEAR_AWARE_PATHS.includes(pathname) || UNIVERSITY_DETAIL_PATH.test(pathname);
}

function GitHubIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

const NAV_LINKS = [
  { label: "Rankings", href: "/" },
  { label: "Analytics", href: "/analytics" },
  { label: "Agent", href: "/agent" },
  { label: "Desk", href: "/desk" },
  { label: "About", href: "/about" },
  { label: "Status", href: "/system-status" },
  { label: "Data Quality", href: "/data-quality" },
];

function navLinkProps(isActive: boolean) {
  return {
    className: "shell-link",
    "aria-current": isActive ? ("page" as const) : undefined,
  };
}

/** Nav links without the query string: what renders before the URL is readable. */
function PlainNavLinks({ pathname }: { pathname: string }) {
  return (
    <>
      {NAV_LINKS.map((link) => (
        <Link key={link.label} href={link.href} {...navLinkProps(pathname === link.href)}>
          {link.label}
        </Link>
      ))}
    </>
  );
}

/** Nav links that keep the edition being viewed when they lead to a year-aware page. */
function YearPreservingNavLinks({ pathname }: { pathname: string }) {
  const searchParams = useSearchParams();
  const { year } = resolveSelectedYear(searchParams?.get(YEAR_QUERY_PARAM));
  return (
    <>
      {NAV_LINKS.map((link) => (
        <Link
          key={link.label}
          href={isYearAwarePath(link.href) ? hrefForEdition(link.href, year) : link.href}
          {...navLinkProps(pathname === link.href)}
        >
          {link.label}
        </Link>
      ))}
    </>
  );
}

export default function NavBar() {
  const pathname = usePathname() ?? "";
  const { authenticated, currentUser, loading, refresh } = useAuth();

  async function handleSignOut() {
    try {
      await fetch("/api/auth/signout", {
        method: "POST",
        credentials: "include",
      });
    } catch {
      /* ignore network errors — state will update anyway */
    }
    await refresh();
  }

  return (
    <nav className="shell-bar" aria-label="Main">
      <div className="shell-bar__inner">
        <div className="shell-bar__left">
          <Link href="/" className="wordmark">
            <Image src="/crawler-watermark.png" alt="" width={28} height={28} priority />
            <span className="wordmark__text">CrawlerNest</span>
          </Link>

          <div className="shell-links">
            {/* useSearchParams in the root layout needs its own boundary, or the
                production build fails for every static page. */}
            <Suspense fallback={<PlainNavLinks pathname={pathname} />}>
              <YearPreservingNavLinks pathname={pathname} />
            </Suspense>
          </div>
        </div>

        {/* Right: edition, then auth actions */}
        <div className="shell-bar__right">
          {isYearAwarePath(pathname) ? (
            <Suspense fallback={<YearSelectorFallback variant="nav" />}>
              <YearSelector variant="nav" />
            </Suspense>
          ) : null}

          <a
            href="https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform"
            target="_blank"
            rel="noopener noreferrer"
            className="shell-icon"
            aria-label="GitHub"
          >
            <GitHubIcon />
          </a>

          {/* Suppress auth area entirely during initial load to avoid flicker */}
          {loading ? (
            <div className="shell-pending" aria-hidden="true" />
          ) : authenticated && currentUser ? (
            /* Authenticated state */
            <>
              <span className="shell-email">{currentUser.email}</span>
              <button onClick={handleSignOut} className="btn btn--secondary">
                Sign out
              </button>
            </>
          ) : (
            /* Unauthenticated state */
            <>
              <Link href="/signup" className="btn shell-hide-sm">
                Sign up
              </Link>
              <Link href="/signin" className="btn btn--secondary">
                Sign in
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
