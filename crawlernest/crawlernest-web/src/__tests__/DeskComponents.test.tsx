import { fireEvent, render, screen } from "@testing-library/react";
import {
  ChatPanel,
  DeskTabBar,
  ResonanceBar,
  ScoreRing,
  SkillMasteryList,
  TaskList,
  deadlineBadge,
  resonanceTier,
} from "@/components/desk";
import { clampPercent, daysUntil } from "@/components/desk/meter";
import { DESK_CHAT_UNREACHABLE, sendDeskPrompt } from "@/lib/deskChat";

const TODAY = new Date("2026-10-18T12:00:00Z");

describe("meter helpers", () => {
  it("clamps out-of-range and non-finite values", () => {
    expect(clampPercent(150)).toBe(100);
    expect(clampPercent(-5)).toBe(0);
    expect(clampPercent(Number.NaN)).toBe(0);
    expect(clampPercent(3, 4)).toBe(75);
  });

  it("counts whole days regardless of the time of day", () => {
    expect(daysUntil("2026-10-18", TODAY)).toBe(0);
    expect(daysUntil("2026-10-25", TODAY)).toBe(7);
    expect(daysUntil("2026-10-15", TODAY)).toBe(-3);
  });
});

describe("ScoreRing", () => {
  it("exposes its value as a meter", () => {
    render(<ScoreRing value={78} label="Overall score" />);
    const meter = screen.getByRole("meter", { name: "Overall score" });
    expect(meter).toHaveAttribute("aria-valuenow", "78");
    expect(screen.getByText("78")).toBeInTheDocument();
  });
});

describe("SkillMasteryList", () => {
  it("marks only the weakest skill as Focus next", () => {
    render(
      <SkillMasteryList
        skills={[
          { label: "Algebra", percent: 94 },
          { label: "Geometry", percent: 58 },
          { label: "Data", percent: 86 },
        ]}
      />,
    );
    expect(screen.getAllByText(/focus next/i)).toHaveLength(1);
    expect(screen.getByText("Geometry").closest("span")).toHaveTextContent(/focus next/i);
  });
});

describe("ResonanceBar", () => {
  it("names the tier for the level", () => {
    expect(resonanceTier(88).label).toBe("Strong");
    expect(resonanceTier(50).label).toBe("Moderate");
    expect(resonanceTier(10).label).toBe("Emerging");
    render(<ResonanceBar trait="Teaching" institution="MIT" level={62} />);
    expect(screen.getByRole("meter", { name: "Teaching resonance with MIT" })).toHaveAttribute(
      "aria-valuetext",
      "Moderate, 62 of 100",
    );
  });
});

describe("TaskList", () => {
  const tasks = [
    { id: "a", title: "Later", dueDate: "2026-12-01", status: "todo" as const },
    { id: "b", title: "Finished", dueDate: "2026-10-01", status: "done" as const },
    { id: "c", title: "Soon", dueDate: "2026-10-20", status: "todo" as const },
  ];

  it("puts open tasks first, by due date", () => {
    render(<TaskList tasks={tasks} today={TODAY} />);
    const titles = screen.getAllByRole("listitem").map((item) => item.querySelector("p")?.textContent);
    expect(titles).toEqual(["Soon", "Later", "Finished"]);
  });

  it("flags overdue and near deadlines but not finished tasks", () => {
    expect(deadlineBadge({ ...tasks[0], dueDate: "2026-10-16" }, TODAY)?.text).toBe("2d overdue");
    expect(deadlineBadge(tasks[2], TODAY)?.text).toBe("2d left");
    expect(deadlineBadge(tasks[1], TODAY)?.text).toBe("Oct 1");
  });
});

describe("ChatPanel", () => {
  it("sends the trimmed prompt on Enter and clears the box", () => {
    const onSend = jest.fn();
    render(<ChatPanel messages={[]} onSend={onSend} />);
    const box = screen.getByLabelText("Prompt");
    fireEvent.change(box, { target: { value: "  help me  " } });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("help me");
    expect(box).toHaveValue("");
  });

  it("does not send an empty prompt or while pending", () => {
    const onSend = jest.fn();
    const { rerender } = render(<ChatPanel messages={[]} onSend={onSend} />);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    rerender(<ChatPanel messages={[]} onSend={onSend} pending />);
    fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: "hi" } });
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});

describe("DeskTabBar", () => {
  it("selects the active tab and moves with arrow keys", () => {
    const onChange = jest.fn();
    render(<DeskTabBar activeTab="desk" onChange={onChange} />);
    const active = screen.getByRole("tab", { name: "Your desk" });
    expect(active).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(active, { key: "ArrowLeft" });
    expect(onChange).toHaveBeenCalledWith("application");
  });
});

describe("sendDeskPrompt", () => {
  function fakeFetch(status: number, body: unknown) {
    return jest.fn().mockResolvedValue({ ok: status < 400, json: async () => body }) as unknown as typeof fetch;
  }

  it("posts to the agent chat route and keeps the warnings", async () => {
    const fetchImpl = fakeFetch(200, {
      success: true,
      data: { data: { explanation: "Here is a plan." }, warnings: ["YEAR_FALLBACK: answer describes 2025"] },
    });
    const reply = await sendDeskPrompt("plan my week", "s1", fetchImpl);
    expect(fetchImpl).toHaveBeenCalledWith("/api/agent/chat", expect.objectContaining({ method: "POST" }));
    expect(JSON.parse((fetchImpl as jest.Mock).mock.calls[0][1].body)).toEqual({ message: "plan my week", session_id: "s1" });
    expect(reply).toEqual({ ok: true, text: "Here is a plan.", warnings: ["YEAR_FALLBACK: answer describes 2025"] });
  });

  it("reports a provider failure as an error, with its message", async () => {
    const reply = await sendDeskPrompt("hi", "s1", fakeFetch(503, { success: false, error: "Provider down" }));
    expect(reply.ok).toBe(false);
    expect(reply.text).toBe("Provider down");
  });

  it("reports an unreachable route", async () => {
    const fetchImpl = jest.fn().mockRejectedValue(new TypeError("network")) as unknown as typeof fetch;
    expect(await sendDeskPrompt("hi", "s1", fetchImpl)).toEqual({ ok: false, text: DESK_CHAT_UNREACHABLE, warnings: [] });
  });
});

describe("ChatPanel replies", () => {
  it("shows the agent's coded disclosures above the reply", () => {
    const warning = "UnsupportedYearWarning: Year 2019 is not available.";
    render(<ChatPanel messages={[{ id: "a", role: "assistant", content: "Answer", warnings: [warning] }]} onSend={jest.fn()} />);
    const banner = screen.getByRole("alert", { name: "Response disclosures" });
    expect(banner).toHaveTextContent("Year 2019 is not available.");
    expect(banner.compareDocumentPosition(screen.getByText("Answer"))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("marks a failed reply as an alert", () => {
    render(<ChatPanel messages={[{ id: "a", role: "assistant", content: "Provider down", error: true }]} onSend={jest.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Provider down");
  });
});
