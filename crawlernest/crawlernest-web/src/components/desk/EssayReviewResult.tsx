import { ScoreBreakdown } from "./ScoreRing";

/** The parts of a stored essay review this component draws. Matches deskApi's EssayReview. */
export interface EssayReviewView {
  essayTitle: string;
  wordCount: number;
  wordLimit: number | null;
  rubricVersion: string;
  overallScore: number;
  dimensions: { key: string; label: string; score: number; rationale: string }[];
  suggestions: { original: string; suggested: string; dimension: string; reason: string }[];
  comparedToRevision: { overallDelta: number; dimensionDeltas: Record<string, number> } | null;
  cached: boolean;
  droppedQuotes: number;
  model: string;
  isEstimated: true;
  caveats: string[];
}

/** Words written against the prompt's limit. Over the limit is flagged, not hidden. */
export function WordProgress({ count, limit }: { count: number; limit: number }) {
  const over = count > limit;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="font-medium text-slate-700">Length</span>
        <span className={`tabular-nums ${over ? "font-semibold text-red-700" : "text-slate-600"}`}>
          {count} of {limit} words{over ? ` · ${count - limit} over` : ""}
        </span>
      </div>
      <div role="meter" aria-label="Words against the limit" aria-valuemin={0} aria-valuemax={limit} aria-valuenow={count}
        className="h-1.5 w-full overflow-hidden bg-slate-200">
        <div className={`h-full rounded-full ${over ? "bg-red-500" : "bg-blue-500"}`}
          style={{ width: `${Math.min(100, (count / limit) * 100)}%` }} />
      </div>
    </div>
  );
}

function Delta({ value }: { value: number | undefined }) {
  if (value === undefined || value === 0) return null;
  const up = value > 0;
  return (
    <span className={`ml-1 text-xs font-semibold tabular-nums ${up ? "text-emerald-700" : "text-red-700"}`}>
      {up ? "+" : ""}{Number.isInteger(value) ? value : value.toFixed(1)}
    </span>
  );
}

/**
 * Scores, rationale and before/after suggestions for one review, with its
 * caveats always shown -- the scores are a model's estimate and the card says so
 * where the numbers are, not in a footnote elsewhere.
 */
export function EssayReviewResult({ review, compact = false }: { review: EssayReviewView; compact?: boolean }) {
  const deltas = review.comparedToRevision?.dimensionDeltas ?? {};
  const labelFor = (key: string) => review.dimensions.find((d) => d.key === key)?.label ?? key;
  return (
    <div className="space-y-4">
      <ScoreBreakdown
        overall={review.overallScore}
        overallLabel="Overall (estimate)"
        subScores={review.dimensions.map((d) => ({ label: d.label, value: d.score }))}
      />
      {review.wordLimit !== null ? <WordProgress count={review.wordCount} limit={review.wordLimit} /> : null}
      {review.comparedToRevision ? (
        <p className="text-sm text-slate-600">
          Compared with the previous draft: overall<Delta value={review.comparedToRevision.overallDelta} />
          {review.comparedToRevision.overallDelta === 0 ? " unchanged" : null}
        </p>
      ) : null}

      {!compact ? (
        <>
          <ul className="space-y-2" aria-label="Dimension feedback">
            {review.dimensions.map((d) => (
              <li key={d.key} className="text-sm">
                <span className="font-semibold text-slate-800">{d.label}</span>
                <span className="tabular-nums text-slate-500"> · {d.score}</span>
                <Delta value={deltas[d.key]} />
                <p className="text-slate-600">{d.rationale}</p>
              </li>
            ))}
          </ul>

          {review.suggestions.length > 0 ? (
            <section aria-label="Suggested revisions" className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-900">Suggested revisions</h3>
              {review.suggestions.map((s, i) => (
                <figure key={i} className="rounded-lg border border-slate-200 p-3 text-sm">
                  <p className="text-slate-500"><span className="font-medium text-slate-700">Before: </span><del className="decoration-red-300">{s.original}</del></p>
                  <p className="mt-1 text-slate-800"><span className="font-medium text-slate-700">After: </span><ins className="no-underline">{s.suggested}</ins></p>
                  <figcaption className="mt-1 text-xs text-slate-500">{labelFor(s.dimension)}: {s.reason}</figcaption>
                </figure>
              ))}
            </section>
          ) : null}
        </>
      ) : null}

      <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
        {review.caveats.map((c) => <p key={c}>{c}</p>)}
        <p className="mt-1 text-slate-500">
          {review.model} · {review.rubricVersion}{review.wordLimit === null ? ` · ${review.wordCount} words` : ""}
          {review.cached ? " · this exact draft was scored before; showing that review" : ""}
          {review.droppedQuotes > 0 ? ` · ${review.droppedQuotes} quote(s) the model gave were not in your draft and are not shown` : ""}
        </p>
      </div>
    </div>
  );
}
