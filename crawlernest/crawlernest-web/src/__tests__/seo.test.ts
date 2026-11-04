import robots from "@/app/robots";
import sitemap from "@/app/sitemap";
import { siteDescription, sourceListText, universityDescription } from "@/lib/seo";
import { absoluteUrl, getSiteUrl, universityPath } from "@/lib/site";
import type { UniversityDetail } from "@/types/university";

const originalFetch = global.fetch;
const originalSiteUrl = process.env.CRAWLERNEST_SITE_URL;

afterEach(() => {
  global.fetch = originalFetch;
  if (originalSiteUrl === undefined) delete process.env.CRAWLERNEST_SITE_URL;
  else process.env.CRAWLERNEST_SITE_URL = originalSiteUrl;
});

function detail(overrides: Partial<UniversityDetail>): UniversityDetail {
  return {
    canonicalUniversityId: 1, slug: "university-of-göttingen", universityName: "University of Göttingen",
    country: "Germany", aggregatedRanking: null, sourceRankings: [], admissionRequirements: {} as UniversityDetail["admissionRequirements"],
    dataQuality: null, rankingYear: 2026, ...overrides,
  };
}

describe("getSiteUrl", () => {
  it("is null when unset, blank, or not http(s), so nothing points at a made-up origin", () => {
    expect(getSiteUrl(undefined)).toBeNull();
    expect(getSiteUrl("  ")).toBeNull();
    expect(getSiteUrl("ftp://crawlernest.example")).toBeNull();
    expect(getSiteUrl("not a url")).toBeNull();
  });

  it("drops a trailing slash, a query and a fragment, and keeps a base path", () => {
    expect(absoluteUrl("/about", getSiteUrl("https://crawlernest.example/"))).toBe("https://crawlernest.example/about");
    expect(absoluteUrl("/about", getSiteUrl("https://x.example/base/?a=1#f"))).toBe("https://x.example/base/about");
    expect(absoluteUrl("/about", null)).toBeNull();
  });

  it("encodes the non-ASCII letters slugs can hold", () => {
    expect(universityPath("university-of-göttingen")).toBe("/universities/university-of-g%C3%B6ttingen");
    expect(universityPath("queen's-university-belfast")).toBe("/universities/queen's-university-belfast");
  });
});

describe("descriptions", () => {
  it("names the ingested sources and no university count", () => {
    expect(sourceListText(["QS", "THE", "ARWU"])).toBe("QS, THE and ARWU");
    expect(sourceListText(["ARWU"])).toBe("ARWU");
    expect(siteDescription()).toContain("QS, THE and ARWU");
    expect(siteDescription()).not.toMatch(/\d,?\d{3}/);
  });

  it("quotes each rank as printed, for the page's edition only", () => {
    const text = universityDescription(detail({
      sourceRankings: [
        { source: "QS", year: 2026, rank: 243, rankDisplay: "243", score: null },
        { source: "THE", year: 2026, rank: 122, rankDisplay: "=122", score: null },
        { source: "ARWU", year: 2026, rank: 151, rankDisplay: "151-200", score: null },
        { source: "QS", year: 2025, rank: 200, rankDisplay: "200", score: null },
      ],
    }));
    expect(text).toBe("University of Göttingen, Germany. 2026 rankings as each source printed them: QS 243, THE =122, ARWU 151-200.");
  });

  it("calls a missing source our gap, not the source's verdict", () => {
    const text = universityDescription(detail({
      sourceRankings: [{ source: "QS", year: 2026, rank: 243, rankDisplay: "243", score: null }],
    }));
    expect(text).toContain("QS 243");
    expect(text).toContain("CrawlerNest holds no THE and ARWU rank for this edition.");
    expect(text).not.toMatch(/unranked|not ranked/i);
  });

  it("says so when nothing is held for the edition", () => {
    expect(universityDescription(detail({}))).toBe(
      "University of Göttingen, Germany. CrawlerNest holds no 2026 ranking for it from QS, THE and ARWU.",
    );
  });
});

describe("robots.txt", () => {
  it("names the sitemap only when the site URL is set", () => {
    delete process.env.CRAWLERNEST_SITE_URL;
    expect(robots().sitemap).toBeUndefined();
    process.env.CRAWLERNEST_SITE_URL = "https://crawlernest.example";
    expect(robots().sitemap).toBe("https://crawlernest.example/sitemap.xml");
  });

  it("keeps account and personal pages and query variants out", () => {
    const rules = robots().rules;
    const all = (Array.isArray(rules) ? rules : [rules]).find((rule) => rule.userAgent === "*");
    expect(all?.disallow).toEqual(expect.arrayContaining(["/api/", "/desk", "/admin", "/signin", "/reset-password", "/*?"]));
    expect(all?.disallow).not.toContain("/universities");
  });
});

describe("sitemap.xml", () => {
  it("is empty without a site URL, and does not call the API", async () => {
    delete process.env.CRAWLERNEST_SITE_URL;
    global.fetch = jest.fn();
    expect(await sitemap()).toEqual([]);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("lists the public pages and every university the API returns", async () => {
    process.env.CRAWLERNEST_SITE_URL = "https://crawlernest.example";
    global.fetch = jest.fn(async () => ({
      ok: true, status: 200,
      json: async () => ({ success: true, data: [
        { slug: "university-of-göttingen", lastModified: "2026-10-12T08:00:00Z" },
        { slug: "mit", lastModified: null },
      ] }),
    })) as unknown as typeof fetch;

    const entries = await sitemap();
    expect(entries.map((e) => e.url)).toEqual([
      "https://crawlernest.example/", "https://crawlernest.example/subject-rankings", "https://crawlernest.example/analytics",
      "https://crawlernest.example/data-quality", "https://crawlernest.example/about",
      "https://crawlernest.example/universities/university-of-g%C3%B6ttingen", "https://crawlernest.example/universities/mit",
    ]);
    expect(entries[5].lastModified).toBe("2026-10-12T08:00:00Z");
    expect(entries[6]).not.toHaveProperty("lastModified");
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toMatch(/\/api\/v1\/universities\/sitemap-entries$/);
  });

  it("still lists the public pages when the API is down", async () => {
    process.env.CRAWLERNEST_SITE_URL = "https://crawlernest.example";
    global.fetch = jest.fn(async () => { throw new Error("ECONNREFUSED"); }) as unknown as typeof fetch;
    const error = jest.spyOn(console, "error").mockImplementation(() => {});
    expect(await sitemap()).toHaveLength(5);
    error.mockRestore();
  });
});
