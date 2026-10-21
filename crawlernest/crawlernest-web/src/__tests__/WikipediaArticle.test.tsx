import { render, screen } from "@testing-library/react";

import { WikipediaArticle } from "@/components/WikipediaArticle";
import type { WikipediaArticle as WikipediaArticleData } from "@/types/university";

const article: WikipediaArticleData = {
  canonicalUniversityId: 1,
  language: "en",
  wikidataId: "Q49108",
  pageTitle: "Massachusetts Institute of Technology",
  pageUrl: "https://en.wikipedia.org/wiki/Massachusetts_Institute_of_Technology",
  revisionId: 123,
  revisionUrl: "https://en.wikipedia.org/w/index.php?title=Massachusetts_Institute_of_Technology&oldid=123",
  revisionTimestamp: "2026-10-01T23:30:00Z",
  matchMethod: "wikidata_source_id",
  license: "CC BY-SA 4.0",
  licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
  fetchedAt: "2026-10-12T00:00:00Z",
  notice: "This text is from Wikipedia and is not CrawlerNest data.",
  sections: [
    { level: 1, heading: null, text: "MIT is a private research university.\nIt was founded in 1861." },
    { level: 2, heading: "History", text: "The charter was signed in 1861." },
    { level: 3, heading: "Early years", text: "Classes began in 1865." },
  ],
};

describe("WikipediaArticle", () => {
  it("shows the lead as paragraphs and the other sections under their headings", () => {
    render(<WikipediaArticle article={article} />);

    expect(screen.getByText("MIT is a private research university.")).toBeInTheDocument();
    expect(screen.getByText("It was founded in 1861.")).toBeInTheDocument();
    expect(screen.getByText("Full article · 2 more sections")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "History" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 4, name: "Early years" })).toBeInTheDocument();
  });

  it("attributes the text: article, revision, licence and the not-our-data notice", () => {
    render(<WikipediaArticle article={article} />);

    expect(screen.getByRole("link", { name: "Massachusetts Institute of Technology" })).toHaveAttribute(
      "href",
      article.pageUrl
    );
    expect(screen.getByRole("link", { name: "revision of 1 October 2026" })).toHaveAttribute("href", article.revisionUrl);
    expect(screen.getByRole("link", { name: "CC BY-SA 4.0" })).toHaveAttribute("href", article.licenseUrl);
    expect(screen.getByText(article.notice)).toBeInTheDocument();
  });

  it("renders markup in the text as text", () => {
    const { container } = render(
      <WikipediaArticle
        article={{ ...article, sections: [{ level: 1, heading: null, text: "<script>alert(1)</script> & <b>bold</b>" }] }}
      />
    );

    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByText("<script>alert(1)</script> & <b>bold</b>")).toBeInTheDocument();
  });

  it("says no article is matched, rather than that none exists", () => {
    render(<WikipediaArticle article={null} />);

    expect(screen.getByText("No Wikipedia article has been matched to this university.")).toBeInTheDocument();
  });
});
