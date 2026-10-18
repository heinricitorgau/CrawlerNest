"use client";

import { useState } from "react";
import { sendDeskPrompt } from "@/lib/deskChat";
import { EssayReviewPanel, LatestEssayCard } from "./EssayReviewPanel";
import { LiveDeadlinesCard, LiveSkillsCard, LiveSprintCard } from "./LiveDeskCards";
import {
  ChatPanel,
  DESK_TABS,
  DeskCard,
  DeskLayout,
  DeskTabBar,
  ResonanceBar,
  ThemeCard,
  type ChatMessage,
} from "@/components/desk";

/*
 * Live: the chat (/api/agent/chat), the sprint and its tasks, skill mastery and
 * essay review (/api/user/desk). Still sample content: the narrative theme and
 * resonance, which have no endpoints yet. They sit under their own banner so
 * nothing sample is shown beside live data without saying so.
 */
function SampleBanner() {
  return (
    <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
      Sample data. The cards below show what narrative analysis will look like. They are not connected to your account yet.
    </p>
  );
}

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
        <SampleBanner />
        <ThemeCard
          title="The Builder Who Teaches"
          summary="You make things, then turn what you learned into something others can use."
          traits={["Maker", "Mentor", "Systems thinker"]}
          evidence={["Robotics team lead", "Weekend coding club for middle schoolers"]}
        />
        <DeskCard eyebrow="Resonance" title="Fit with target schools">
          <div className="space-y-4">
            <ResonanceBar trait="Hands-on building" institution="MIT" level={88} />
            <ResonanceBar trait="Teaching others" institution="Stanford" level={62} />
            <ResonanceBar trait="Community impact" institution="Caltech" level={41} note="Few examples of this yet." />
          </div>
        </DeskCard>
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
