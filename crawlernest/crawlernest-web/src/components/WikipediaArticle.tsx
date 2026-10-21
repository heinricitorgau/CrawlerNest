import type { WikipediaArticle as WikipediaArticleData, WikipediaSection } from "@/types/university";

/**
 * A university's Wikipedia article: the lead in full, the remaining sections folded.
 *
 * The text is rendered as text. It arrives as a plain-text extract, so nothing here
 * interprets markup, and the attribution line is part of the component rather than
 * something a caller can forget: the licence requires it wherever the text appears.
 */
type WikipediaArticleProps = {
  article: WikipediaArticleData | null;
};

function paragraphs(text: string): string[] {
  return text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function SectionBody({ section }: { section: WikipediaSection }) {
  return (
    <>
      {paragraphs(section.text).map((paragraph, index) => (
        <p key={index} className="text-sm leading-7 text-slate-700 [overflow-wrap:anywhere]">
          {paragraph}
        </p>
      ))}
    </>
  );
}

function formatRevisionDate(value: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  // A fixed locale and zone: the server renders this, and a date that depends on
  // where the server runs would differ between deployments.
  return Number.isNaN(parsed.getTime())
    ? null
    : parsed.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}

export function WikipediaArticle({ article }: WikipediaArticleProps) {
  if (!article || article.sections.length === 0) {
    // "Matched" on purpose: an empty result is our matching, not Wikipedia lacking an article.
    return (
      <p className="text-sm italic text-slate-400">
        No Wikipedia article has been matched to this university.
      </p>
    );
  }

  const [first, ...others] = article.sections;
  const lead = first.heading == null ? first : null;
  const rest = lead ? others : article.sections;
  const revisionDate = formatRevisionDate(article.revisionTimestamp);

  return (
    <div>
      {lead && (
        <div className="space-y-4">
          <SectionBody section={lead} />
        </div>
      )}

      {rest.length > 0 && (
        <details className="group mt-6 rounded border border-slate-200">
          <summary className="cursor-pointer select-none px-4 py-3 text-xs font-bold uppercase tracking-[0.12em] text-slate-600 hover:text-blue-700">
            Full article · {rest.length} more section{rest.length === 1 ? "" : "s"}
          </summary>
          <div className="space-y-4 border-t border-slate-100 px-4 py-4">
            {rest.map((section, index) => (
              <div key={`${index}-${section.heading ?? "lead"}`} className="space-y-3">
                {section.heading &&
                  (section.level <= 2 ? (
                    <h3 className="pt-2 text-base font-bold text-slate-900">{section.heading}</h3>
                  ) : (
                    <h4 className="text-sm font-bold text-slate-700">{section.heading}</h4>
                  ))}
                <SectionBody section={section} />
              </div>
            ))}
          </div>
        </details>
      )}

      <footer className="mt-6 border-t border-slate-100 pt-4 text-xs leading-5 text-slate-500">
        <p>
          From{" "}
          <a href={article.pageUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-700">
            {article.pageTitle}
          </a>{" "}
          on Wikipedia (
          <a href={article.revisionUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-700">
            {revisionDate ? `revision of ${revisionDate}` : "this revision"}
          </a>
          ), available under{" "}
          <a href={article.licenseUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-700">
            {article.license}
          </a>
          . Tables, images and references are not reproduced.
        </p>
        <p className="mt-1">{article.notice}</p>
      </footer>
    </div>
  );
}
