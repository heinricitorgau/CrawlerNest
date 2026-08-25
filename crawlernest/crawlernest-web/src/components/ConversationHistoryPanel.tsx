"use client";

import { useCallback, useEffect, useState } from "react";

import { formatTimestamp } from "@/lib/format";
import {
  deleteConversation,
  getConversationById,
  getConversations,
  type ConversationDetail,
  type ConversationSummary,
} from "@/lib/conversationsApi";

type PanelState =
  | { phase: "loading" }
  | { phase: "ok"; items: ConversationSummary[] }
  | { phase: "unauthenticated" }
  | { phase: "error"; message: string };

export type ConversationHistoryPanelProps = {
  onClose: () => void;
  /** Called with the full transcript once the user picks one to restore. */
  onLoad: (detail: ConversationDetail) => void;
  /** Lets the page prompt for a fresh sign-in when the session has expired. */
  onSessionExpired?: () => void;
  /** Highlights the conversation currently in the chat window, when there is one. */
  activeSessionId?: string;
};

/**
 * Modal list of the transcripts this user has saved.
 *
 * A modal rather than a permanent sidebar because the agent page already gives
 * its right column to run metadata, and history is something the user reaches
 * for occasionally rather than reads alongside the conversation.
 *
 * Mounted only while open, so a page that is never asked for history never
 * calls the API, and reopening always shows a freshly fetched list rather than
 * whatever was on screen last time.
 */
export function ConversationHistoryPanel({
  onClose,
  onLoad,
  onSessionExpired,
  activeSessionId,
}: ConversationHistoryPanelProps) {
  const [state, setState] = useState<PanelState>({ phase: "loading" });
  /**
   * The row request in flight, if any.
   *
   * One at a time on purpose. Two overlapping requests would race on this very
   * state -- whichever finished first would clear it and re-enable the buttons
   * while the other was still running -- and a second Delete fired during a
   * Load would remove a row the user is in the middle of opening.
   */
  const [busy, setBusy] = useState<{ id: number; action: "load" | "delete" } | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  /**
   * Applies a list result. Split from the fetch so the mount effect can await
   * before touching state: setting it synchronously inside an effect triggers
   * the cascading render that react-hooks/set-state-in-effect warns about.
   */
  const applyListResult = useCallback(
    (result: Awaited<ReturnType<typeof getConversations>>) => {
      if (result.ok) {
        setState({ phase: "ok", items: result.data });
        return;
      }
      if (result.reason === "unauthenticated") {
        setState({ phase: "unauthenticated" });
        onSessionExpired?.();
        return;
      }
      setState({ phase: "error", message: result.message });
    },
    [onSessionExpired]
  );

  useEffect(() => {
    // The panel is mounted only while open, so this runs once per opening.
    let cancelled = false;
    void (async () => {
      const result = await getConversations();
      if (!cancelled) {
        applyListResult(result);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyListResult]);

  // Escape closes the panel, which is the shortcut a modal is expected to have
  // and the only way out for someone not using a mouse.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  /**
   * Refetches the list, leaving any row-level message alone.
   *
   * Kept separate from {@link retry} because the not_found path below sets a
   * message and then refetches: folding the two together clears the very
   * explanation the user needs for why a row disappeared.
   */
  const refetchList = useCallback(async () => {
    setState({ phase: "loading" });
    applyListResult(await getConversations());
  }, [applyListResult]);

  /** Retry from the error state. An event handler, so setting state here is fine. */
  async function retry() {
    setRowError(null);
    await refetchList();
  }

  async function handleLoad(id: number) {
    // Belt and braces: the buttons are already disabled, but a double-fire from
    // a fast double-click or a keyboard repeat would otherwise slip through.
    if (busy) {
      return;
    }
    setBusy({ id, action: "load" });
    setRowError(null);
    const result = await getConversationById(id);
    setBusy(null);

    if (result.ok) {
      onLoad(result.data);
      onClose();
      return;
    }
    if (result.reason === "unauthenticated") {
      setState({ phase: "unauthenticated" });
      onSessionExpired?.();
      return;
    }
    if (result.reason === "not_found") {
      // Deleted in another tab since this list was fetched.
      setRowError("That conversation is no longer available.");
      void refetchList();
      return;
    }
    setRowError(result.message);
  }

  async function handleDelete(id: number) {
    if (busy) {
      return;
    }
    setBusy({ id, action: "delete" });
    setRowError(null);
    const result = await deleteConversation(id);
    setBusy(null);

    if (result.ok) {
      // Drop it locally rather than refetching: the row is gone either way, and
      // a refetch would make the whole list flash for one deletion.
      setState((current) =>
        current.phase === "ok"
          ? { phase: "ok", items: current.items.filter((item) => item.id !== id) }
          : current
      );
      return;
    }
    if (result.reason === "unauthenticated") {
      setState({ phase: "unauthenticated" });
      onSessionExpired?.();
      return;
    }
    if (result.reason === "not_found") {
      setState((current) =>
        current.phase === "ok"
          ? { phase: "ok", items: current.items.filter((item) => item.id !== id) }
          : current
      );
      return;
    }
    setRowError(result.message);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-[#1a1a1a]/40 px-4 py-10"
      role="presentation"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Saved conversations"
        className="w-full max-w-2xl overflow-hidden rounded-[1.5rem] border border-[#d8d3cb] bg-white shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center justify-between gap-4 border-b border-[#e8e4dd] px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-[#16382a]">Saved conversations</h2>
            <p className="mt-1 text-sm text-[#6b7068]">
              Load one to pick the thread back up, or remove it from your account.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[#d8d3cb] bg-white px-3 py-1 text-sm text-[#6b7068] transition hover:border-[#a33a3a] hover:text-[#a33a3a]"
          >
            Close
          </button>
        </header>

        <div className="max-h-[60vh] overflow-y-auto px-6 py-5">
          {rowError ? (
            <p
              role="status"
              className="mb-4 rounded-[1rem] border border-[#e2c4bd] bg-[#fbefeb] px-4 py-2 text-sm text-[#8b3a2b]"
            >
              {rowError}
            </p>
          ) : null}

          {state.phase === "loading" ? (
            <p className="text-sm text-[#6b7068]">Loading your saved conversations…</p>
          ) : null}

          {state.phase === "unauthenticated" ? (
            <p className="text-sm text-[#6b7068]">
              Your session has expired. Sign in again to see your saved conversations.
            </p>
          ) : null}

          {state.phase === "error" ? (
            <div className="space-y-3">
              <p className="text-sm text-[#8b3a2b]">{state.message}</p>
              <button
                type="button"
                onClick={() => void retry()}
                className="rounded-full border border-[#d8d3cb] bg-white px-3 py-1 text-sm text-[#1a3d2e] transition hover:border-[#3d7a5a]"
              >
                Try again
              </button>
            </div>
          ) : null}

          {state.phase === "ok" && state.items.length === 0 ? (
            <p className="text-sm text-[#6b7068]">
              You have not saved a conversation yet. Use “Save conversation” after a
              chat and it will appear here.
            </p>
          ) : null}

          {state.phase === "ok" && state.items.length > 0 ? (
            <ul className="space-y-3">
              {state.items.map((item) => {
                const isActive = Boolean(activeSessionId) && item.sessionId === activeSessionId;
                // Every row locks while any request is in flight, not just the
                // row that started it: the alternative lets a user delete row B
                // while row A is still loading.
                const anyBusy = busy !== null;
                const loadingThis = busy?.id === item.id && busy.action === "load";
                const deletingThis = busy?.id === item.id && busy.action === "delete";
                return (
                  <li
                    key={item.id}
                    className={`rounded-[1.25rem] border px-4 py-3 transition ${
                      isActive
                        ? "border-[#3d7a5a] bg-[#f2f8f4]"
                        : "border-[#e8e4dd] bg-[#faf8f4]"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="truncate font-medium text-[#1a1a1a]">{item.title}</h3>
                          {isActive ? (
                            <span className="rounded-full bg-[#e8f2ec] px-2 py-0.5 text-xs font-semibold text-[#1a3d2e]">
                              On screen
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1 text-xs text-[#6b7068]">
                          {formatTimestamp(item.updatedAt)} · {item.turnCount}{" "}
                          {item.turnCount === 1 ? "turn" : "turns"}
                        </p>
                        {item.preview ? (
                          <p className="mt-2 line-clamp-2 text-sm text-[#6b7068]">{item.preview}</p>
                        ) : null}
                      </div>

                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          type="button"
                          onClick={() => void handleLoad(item.id)}
                          disabled={anyBusy}
                          aria-busy={loadingThis}
                          className="rounded-full border border-[#d8d3cb] bg-white px-3 py-1 text-sm text-[#1a3d2e] transition hover:border-[#3d7a5a] disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {loadingThis ? "Loading…" : "Load"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDelete(item.id)}
                          disabled={anyBusy}
                          aria-busy={deletingThis}
                          aria-label={deletingThis ? "Deleting…" : `Delete ${item.title}`}
                          className="rounded-full border border-[#d8d3cb] bg-white px-3 py-1 text-sm text-[#6b7068] transition hover:border-[#a33a3a] hover:text-[#a33a3a] disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {deletingThis ? "Deleting…" : "Delete"}
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default ConversationHistoryPanel;
