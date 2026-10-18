"use client";

import { useState } from "react";
import { sendDeskPrompt } from "@/lib/deskChat";
import {
  ChatPanel,
  DESK_TABS,
  DeskCard,
  DeskLayout,
  DeskTabBar,
  ResonanceBar,
  ScoreBreakdown,
  SkillMasteryList,
  SprintCard,
  ThemeCard,
  type ChatMessage,
  type PrioritySprint,
} from "@/components/desk";

/*
 * The chat is live: it goes to /api/agent/chat. The cards on the right are sample
 * content for the component set -- there is no backend for essays, sprints or
 * test prep yet -- and the banner says so.
 */
const SAMPLE_SPRINT: PrioritySprint = {
  title: "Early Action push",
  goal: "Lock the personal statement and the activities list before EA deadlines.",
  startDate: "2026-10-12",
  endDate: "2026-11-01",
  tasks: [
    { id: "t1", title: "Final draft of personal statement", dueDate: "2026-10-22", status: "in_progress", category: "Essay" },
    { id: "t2", title: "Request counselor recommendation", dueDate: "2026-10-15", status: "done", category: "Recommendations" },
    { id: "t3", title: "Trim activities descriptions to 150 chars", dueDate: "2026-10-20", status: "todo", category: "Activities" },
    { id: "t4", title: "Submit EA application", dueDate: "2026-11-01", status: "todo", category: "Application" },
  ],
};

function SampleBanner() {
  return (
    <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
      Sample data. The cards below show the desk components and are not connected to your account. The chat on the left is the live agent.
    </p>
  );
}

export default function DeskPage() {
  const [activeTab, setActiveTab] = useState("desk");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [sprint, setSprint] = useState(SAMPLE_SPRINT);
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

  function toggleTask(taskId: string) {
    setSprint((prev) => ({
      ...prev,
      tasks: prev.tasks.map((task) =>
        task.id === taskId ? { ...task, status: task.status === "done" ? "todo" : "done" } : task,
      ),
    }));
  }

  const activeLabel = DESK_TABS.find((tab) => tab.id === activeTab)?.label ?? "";

  const panel =
    activeTab === "desk" ? (
      <>
        <SampleBanner />
        <SprintCard sprint={sprint} today={today} onToggleTask={toggleTask} />
        <DeskCard eyebrow="Essay review" title="Personal statement">
          <ScoreBreakdown
            overall={78}
            subScores={[
              { label: "Impact", value: 82 },
              { label: "Introspection", value: 64 },
              { label: "Voice", value: 85 },
              { label: "Structure", value: 79 },
            ]}
          />
        </DeskCard>
        <DeskCard eyebrow="Test prep" title="SAT Math mastery">
          <SkillMasteryList
            skills={[
              { label: "Algebra", percent: 94 },
              { label: "Advanced math", percent: 86 },
              { label: "Problem solving & data", percent: 71 },
              { label: "Geometry & trig", percent: 58 },
            ]}
          />
        </DeskCard>
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
