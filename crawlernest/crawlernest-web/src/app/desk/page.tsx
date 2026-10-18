"use client";

import { useState } from "react";
import { sendDeskPrompt } from "@/lib/deskChat";
import { EssayReviewPanel, LatestEssayCard } from "./EssayReviewPanel";
import { LiveDeadlinesCard, LiveSkillsCard, LiveSprintCard } from "./LiveDeskCards";
import { LiveNarrativeCard } from "./LiveNarrativeCard";
import {
  ChatPanel,
  DESK_TABS,
  DeskCard,
  DeskLayout,
  DeskTabBar,
  type ChatMessage,
} from "@/components/desk";

/*
 * Every card here is live: the chat (/api/agent/chat) and the desk API
 * (/api/user/desk) -- sprint and tasks, deadlines, skills, essay review, and the
 * narrative. Nothing on this page is sample data any more.
 */
export default function DeskPage() {
  const [activeTab, setActiveTab] = useState("desk");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [today] = useState(() => new Date());

  async function handleSend(prompt: string) {
    const id = crypto.randomUUID();
    setMessages((prev) => [...prev, { id: `${id}-q`, role: "user", content: prompt }]);
    setPending(true);
    const reply = await sendDeskPrompt(prompt, sessionId);
    setMessages((prev) => [
      ...prev,
      { id: `${id}-a`, role: "assistant", content: reply.text, warnings: reply.warnings, error: !reply.ok },
    ]);
    setPending(false);
  }

  const activeLabel = DESK_TABS.find((tab) => tab.id === activeTab)?.label ?? "";

  const panel =
    activeTab === "desk" ? (
      <>
        <LiveSprintCard today={today} />
        <LiveDeadlinesCard today={today} />
        <LiveSkillsCard />
        <LatestEssayCard onOpenReviews={() => setActiveTab("essay-review")} />
        <LiveNarrativeCard />
      </>
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
      chat={<ChatPanel messages={messages} onSend={handleSend} pending={pending} />}
      panel={panel}
      tabBar={<DeskTabBar activeTab={activeTab} onChange={setActiveTab} />}
    />
  );
}
