"use client";

import { useState } from "react";
import type { ChatAction, ChatActionDecision } from "./types";

const STATUS: Record<ChatAction["status"], { label: string; className: string }> = {
  applied: { label: "Done", className: "bg-emerald-50 text-emerald-800 ring-emerald-200" },
  proposed: { label: "Waiting for you", className: "bg-amber-50 text-amber-900 ring-amber-200" },
  confirmed: { label: "Confirmed", className: "bg-emerald-50 text-emerald-800 ring-emerald-200" },
  rejected: { label: "Rejected", className: "bg-slate-50 text-slate-600 ring-slate-200" },
  undone: { label: "Undone", className: "bg-slate-50 text-slate-600 ring-slate-200" },
  failed: { label: "Didn't happen", className: "bg-red-50 text-red-800 ring-red-200" },
};

const TOOL_LABEL: Record<string, string> = {
  create_action_task: "Task",
  update_target_list: "School list",
  generate_narrative_themes: "Narrative themes",
};

/**
 * One thing Tassel asked to change, as it actually ended up -- the record of what
 * happened, drawn from the API's status rather than from the reply's wording.
 */
export function ActionCard({ action, onDecide }: {
  action: ChatAction;
  /** Resolves to the action's new state, or to an error message to show. */
  onDecide?: (action: ChatAction, decision: ChatActionDecision) => Promise<ChatAction | string>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const status = STATUS[action.status];

  async function decide(decision: ChatActionDecision) {
    if (!onDecide || busy) return;
    setBusy(true);
    const result = await onDecide(action, decision);
    setBusy(false);
    setError(typeof result === "string" ? result : null);
  }

  const buttons =
    action.id && onDecide
      ? action.status === "proposed"
        ? [["confirm", "Confirm"], ["reject", "Reject"]] as const
        : action.status === "applied"
          ? [["undo", "Undo"]] as const
          : []
      : [];

  return (
    <div className={`rounded-lg px-3 py-2 text-xs ring-1 ${status.className}`} data-status={action.status}>
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold">{TOOL_LABEL[action.tool] ?? action.tool} · {status.label}</span>
        <span className="flex gap-1">
          {buttons.map(([decision, label]) => (
            <button key={decision} type="button" disabled={busy} onClick={() => decide(decision)}
              className="rounded-md bg-white/80 px-2 py-0.5 font-medium ring-1 ring-inset ring-current/20 hover:bg-white disabled:opacity-50">
              {label}
            </button>
          ))}
        </span>
      </div>
      {action.message ? <p className="mt-1 leading-relaxed">{action.message}</p> : null}
      {error ? <p role="alert" className="mt-1 text-red-700">{error}</p> : null}
    </div>
  );
}
