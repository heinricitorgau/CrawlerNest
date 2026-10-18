"use client";

import { useState } from "react";
import { decideChatAction, sendTasselMessage, type TasselTurn } from "@/lib/deskApi";
import { EssayReviewPanel, LatestEssayCard } from "./EssayReviewPanel";
import { LiveDeadlinesCard, LiveSkillsCard, LiveSprintCard } from "./LiveDeskCards";
import { LiveNarrativeCard } from "./LiveNarrativeCard";
import {
  ChatPanel,
  DESK_TABS,
  DeskCard,
  DeskLayout,
  DeskTabBar,
  type ChatAction,
  type ChatActionDecision,
  type ChatMessage,
} from "@/components/desk";

/*
 * Every card here is live, and the chat is Tassel (/api/user/desk/chat): the API
 * runs the tool loop, and each reply carries the changes it made with their real
 * statuses. When a change lands, the cards are remounted so they read it back.
 */

/** The history sent with each turn: the recent exchange, without failed turns. */
const HISTORY_TURNS = 20;

function modeFor(tab: string): "general" | "brainstorming" | "review" {
  return tab === "brainstorming" ? "brainstorming" : tab === "essay-review" ? "review" : "general";
}
export default function DeskPage() {
  const [activeTab, setActiveTab] = useState("desk");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [today] = useState(() => new Date());
  // Bumped when Tassel or the user changes desk data from the chat, so cards re-read it.
  const [revision, setRevision] = useState(0);

  async function handleSend(prompt: string) {
    const id = crypto.randomUUID();
    const history: TasselTurn[] = messages
      .filter((m) => !m.error)
      .slice(-HISTORY_TURNS)
      .map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { id: `${id}-q`, role: "user", content: prompt }]);
    setPending(true);
    const result = await sendTasselMessage({ sessionId, message: prompt, history, mode: modeFor(activeTab) });
    setPending(false);
    if (!result.ok) {
      const content = result.reason === "unauthenticated" ? "Sign in to talk to Tassel." : result.message;
      setMessages((prev) => [...prev, { id: `${id}-a`, role: "assistant", content, error: true }]);
      return;
    }
    setMessages((prev) => [...prev, { id: `${id}-a`, role: "assistant", content: result.data.text, actions: result.data.actions }]);
    if (result.data.actions.some((a) => a.status === "applied")) setRevision((n) => n + 1);
  }

  async function handleDecide(action: ChatAction, decision: ChatActionDecision): Promise<ChatAction | string> {
    if (!action.id) return "This change was not recorded, so it cannot be changed.";
    const result = await decideChatAction(action.id, decision);
    if (!result.ok || !result.data) return result.ok ? "The change could not be read back." : result.message;
    const updated: ChatAction = { ...action, status: result.data };
    setMessages((prev) => prev.map((m) => (m.actions
      ? { ...m, actions: m.actions.map((a) => (a.id === action.id ? updated : a)) }
      : m)));
    setRevision((n) => n + 1);
    return updated;
  }

  const activeLabel = DESK_TABS.find((tab) => tab.id === activeTab)?.label ?? "";

  const panel =
    activeTab === "desk" ? (
      <div key={revision} className="space-y-4">
        <LiveSprintCard today={today} />
        <LiveDeadlinesCard today={today} />
        <LiveSkillsCard />
        <LatestEssayCard onOpenReviews={() => setActiveTab("essay-review")} />
        <LiveNarrativeCard />
      </div>
    ) : activeTab === "essay-review" ? (
      <EssayReviewPanel />
    ) : (
      <DeskCard title={activeLabel}>
        <p className="text-sm text-slate-500">This section is not built yet.</p>
      </DeskCard>
    );

  return (
    <DeskLayout
      activeTab={activeTab}
      chat={
        <ChatPanel
          title="Tassel"
          placeholder="Plan, brainstorm, or ask about a draft…"
          messages={messages}
          onSend={handleSend}
          onDecide={handleDecide}
          pending={pending}
        />
      }
      panel={panel}
      tabBar={<DeskTabBar activeTab={activeTab} onChange={setActiveTab} />}
    />
  );
}
