"use client";

import { useEffect, useState } from "react";

export type ExplanationItem = Record<string, unknown>;

export type ExplanationTaskKind =
  | "recommendation"
  | "ranking_explain"
  | "university_lookup"
  | "data_query"
  | "comparison"
  | "application_plan";

export type RecommendationExplanationProps = {
  /** The rows currently on screen. The agent explains exactly these. */
  items: ExplanationItem[];
  caveats?: string[];
  profile?: Record<string, unknown>;
  /** The already-grouped plan, for the application_plan kind. */
  plan?: Record<string, unknown>;
  query?: string;
  /** What the user said they care about, for the comparison kind. */
  criterion?: string;
  taskKind?: ExplanationTaskKind;
  /** Heading for the panel. */
  title?: string;
};

type ExplanationState = {
  /** Which set of rows this result belongs to, so stale results never render. */
  key: string;
  paragraphs: string[];
  modelName: string | null;
};

/**
 * Model-written explanation of the results already on screen.
 *
 * This is a progressive enhancement and never part of the data path. The rows,
 * ranks, scores, and confidence come from the deterministic engine; the model
 * only writes prose about them, and the agent is sent the displayed rows rather
 * than re-querying, so the text cannot describe a different result set.
 *
 * Nothing is rendered unless the model actually produced the text
 * (`source === "llm"`). When the agent is unreachable or no model is
 * configured, the page looks exactly as it does without this component instead
 * of showing deterministic text dressed up as an explanation.
 */
export default function RecommendationExplanation({
  items,
  caveats,
  profile,
  plan,
  query,
  criterion,
  taskKind = "recommendation",
  title = "Why these results",
}: RecommendationExplanationProps) {
  const [result, setResult] = useState<ExplanationState | null>(null);

  // Refetch only when the displayed evidence actually changes.
  const itemsKey = JSON.stringify({ items, plan: plan ?? null });
  const caveatsKey = JSON.stringify(caveats ?? []);
  // Plan-based kinds carry their evidence as a mapping rather than rows.
  const hasEvidence =
    (items && items.length > 0) || (plan != null && Object.keys(plan).length > 0);

  useEffect(() => {
    if (!hasEvidence) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    // Every state update happens after an await, so switching rows never
    // triggers a synchronous cascade; stale answers are filtered out by key.
    (async () => {
      const empty: ExplanationState = { key: itemsKey, paragraphs: [], modelName: null };
      try {
        const response = await fetch("/api/agent/explain", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({ taskKind, items, caveats, profile, plan, query, criterion }),
        });
        if (!response.ok) {
          if (active) setResult(empty);
          return;
        }
        const body = await response.json();
        const data = body?.data;
        // Only surface text the model actually wrote.
        if (body?.success && data?.source === "llm") {
          const paragraphs: string[] = Array.isArray(data.paragraphs)
            ? data.paragraphs.filter((p: unknown) => typeof p === "string" && p.trim())
            : [];
          if (active) {
            setResult({ key: itemsKey, paragraphs, modelName: data.modelName ?? null });
          }
        } else if (active) {
          setResult(empty);
        }
      } catch {
        // An unreachable agent is not an error for the page.
        if (active) setResult(empty);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemsKey, caveatsKey, taskKind, query]);

  // A result belonging to a previous evidence set counts as "still loading".
  const explanation = result && result.key === itemsKey ? result : null;

  if (hasEvidence && explanation === null) {
    return (
      <div className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-500">
        Preparing an explanation of these results…
      </div>
    );
  }

  if (!explanation || explanation.paragraphs.length === 0) {
    return null;
  }

  return (
    <section
      aria-label={title}
      className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900"
    >
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="font-medium">{title}</span>
        <span className="text-xs text-blue-700">
          Written by a local model
          {explanation.modelName ? ` (${explanation.modelName})` : ""}
        </span>
      </div>
      <div className="space-y-2">
        {explanation.paragraphs.map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>
      <p className="mt-3 text-xs text-blue-700">
        Ranks, scores, and confidence come from the ranking data — the model only
        describes them.
      </p>
    </section>
  );
}
