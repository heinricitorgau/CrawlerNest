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
      className={`rounded-2xl border border-[#ecd9b8] bg-[#fbf7ec] px-4 py-3 text-xs leading-5 text-[#6b5a36] ${className}`.trim()}
    >
      <p className="font-semibold uppercase tracking-[0.12em] text-[#8a6116]">{title}</p>
      <ul className="mt-2 list-disc space-y-1 pl-4 [overflow-wrap:anywhere]">
        {shown.map((caveat) => (
          <li key={caveat}>{caveat}</li>
        ))}
      </ul>
    </aside>
  );
}
