"use client";

import { useEffect, useState } from "react";
import { getModelUsage, type ModelUsage } from "@/lib/deskApi";

/** Below this share of the day's budget, the line turns amber. */
const LOW_SHARE = 0.1;

/**
 * One line above the desk panel: how many model calls the user has left in the last 24 hours
 * (GET /api/user/desk/usage). Remount it (change its key) after anything that may call the model.
 *
 * Shows nothing while loading, when signed out (the cards already ask to sign in), or when the usage cannot be read:
 * it is a convenience, and an error line here would only repeat the card's own.
 */
export function ModelUsageNotice() {
  const [usage, setUsage] = useState<ModelUsage | null>(null);

  useEffect(() => {
    let live = true;
    void getModelUsage().then((result) => {
      if (live && result.ok) setUsage(result.data);
    });
    return () => {
      live = false;
    };
  }, []);

  if (!usage) return null;

  const tokens = usage.promptTokens + usage.completionTokens;
  const detail = [
    "Counted over the last 24 hours. An essay review or a theme run uses up to 2, a Tassel reply up to 4.",
    tokens > 0 || usage.callsWithoutUsage > 0
      ? `${usage.callsWithoutUsage > 0 ? "At least " : ""}${tokens.toLocaleString("en-US")} tokens used.`
      : null,
    usage.unreachableCalls > 0
      ? `${usage.unreachableCalls} call${usage.unreachableCalls === 1 ? "" : "s"} could not reach the model and did not count.`
      : null,
  ].filter(Boolean).join(" ");

  if (usage.perDay === null || usage.left === null) {
    return (
      <p className="text-xs text-slate-500" data-testid="model-usage">
        Model calls in the last 24 hours: <span className="font-medium text-slate-700">{usage.modelCalls}</span> (no
        limit set). <span className="text-slate-400">{detail}</span>
      </p>
    );
  }

  const low = usage.left <= usage.perDay * LOW_SHARE;
  return (
    <p
      className={`rounded-md border px-3 py-2 text-xs ${low ? "border-amber-200 bg-amber-50 text-amber-800" : "border-slate-200 bg-white text-slate-600"}`}
      data-testid="model-usage"
    >
      Model calls left today:{" "}
      <span className="font-semibold tabular-nums">
        {usage.left} / {usage.perDay}
      </span>
      {usage.left === 0 ? " — the next AI request will be refused until earlier calls age out." : null}{" "}
      <span className={low ? "text-amber-700" : "text-slate-400"}>{detail}</span>
    </p>
  );
}
