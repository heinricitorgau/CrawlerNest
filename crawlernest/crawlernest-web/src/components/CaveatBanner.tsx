/**
 * A list of data caveats, rendered verbatim.
 *
 * Takes strings, never builds them: every caveat comes from `caveatMessages.ts` or
 * from an API response, which is what keeps the text identical to the Java and
 * Python copies the contract test compares. Duplicates are dropped (a page merging
 * its own caveats with an API's can hold the same string twice); order is kept.
 */
type CaveatBannerProps = {
  caveats: ReadonlyArray<string | null | undefined>;
  title?: string;
  className?: string;
};

export function CaveatBanner({ caveats, title = "Data caveats", className = "" }: CaveatBannerProps) {
  const shown = [...new Set(caveats.filter((caveat): caveat is string => Boolean(caveat && caveat.trim())))];
  if (shown.length === 0) {
    return null;
  }
  return (
    <aside
      role="note"
      aria-label={title}
      className={`caveats ${className}`.trim()}
    >
      <p className="caveats__title">{title}</p>
      <ul className="caveats__list">
        {shown.map((caveat) => (
          <li key={caveat}>{caveat}</li>
        ))}
      </ul>
    </aside>
  );
}
