"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import AgentWarningBanner from "@/components/AgentWarningBanner";
import type { ChatMessage } from "./types";

interface ChatPanelProps {
  messages: ChatMessage[];
  onSend: (prompt: string) => void;
  pending?: boolean;
  title?: string;
  placeholder?: string;
}

/** Message list that scrolls, with the prompt box pinned to the bottom. Enter sends, Shift+Enter breaks a line. */
export function ChatPanel({
  messages,
  onSend,
  pending = false,
  title = "Counselor",
  placeholder = "Ask about your application...",
}: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length]);

  const canSend = draft.trim().length > 0 && !pending;

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!canSend) return;
    onSend(draft.trim());
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      submit();
      event.preventDefault();
    }
  }

  return (
    <section aria-label={title} className="flex h-full min-h-0 flex-col rounded-xl border border-slate-200 bg-white">
      <header className="flex items-center gap-2 border-b border-slate-200 px-4 py-3">
        <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
        {messages.length === 0 ? (
          <p className="pt-8 text-center text-sm text-slate-400">Start by asking a question.</p>
        ) : null}
        {messages.map((message) =>
          message.role === "user" ? (
            <div key={message.id} className="flex justify-end">
              <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-slate-900 px-4 py-2 text-sm leading-relaxed text-white">
                {message.content}
              </p>
            </div>
          ) : (
            <div key={message.id} className="max-w-[85%]">
              {/* Disclosures sit above the reply they qualify, as on /agent. */}
              <AgentWarningBanner warnings={message.warnings} />
              <p
                role={message.error ? "alert" : undefined}
                className={`whitespace-pre-wrap rounded-2xl rounded-bl-sm px-4 py-2 text-sm leading-relaxed ${
                  message.error ? "border border-red-200 bg-red-50 text-red-700" : "bg-slate-100 text-slate-800"
                }`}
              >
                {message.content}
              </p>
            </div>
          ),
        )}
        {pending ? <p className="text-xs text-slate-400">Thinking…</p> : null}
        <div ref={endRef} />
      </div>

      <form onSubmit={submit} className="border-t border-slate-200 p-3">
        <div className="flex items-end gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100">
          <label htmlFor="desk-prompt" className="sr-only">Prompt</label>
          <textarea
            id="desk-prompt"
            rows={1}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="max-h-40 flex-1 resize-none bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
          />
          <button
            type="submit"
            disabled={!canSend}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            Send
          </button>
        </div>
      </form>
    </section>
  );
}
