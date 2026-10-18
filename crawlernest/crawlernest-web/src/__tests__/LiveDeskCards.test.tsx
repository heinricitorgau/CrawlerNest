import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { LiveSkillsCard, LiveSprintCard } from "@/app/desk/LiveDeskCards";
import { toDeskTask, toSkills, toSprint } from "@/lib/deskApi";

const TODAY = new Date("2026-10-18T12:00:00Z");
const originalFetch = global.fetch;

function respond(status: number, body: unknown) {
  return { ok: status < 400, status, json: async () => body } as Response;
}

const SPRINT = {
  sprint: { id: 3, title: "Early Action push", goal: "Lock the essay", startDate: "2026-10-12", endDate: "2026-11-01",
    taskCount: 2, doneCount: 1 },
  tasks: [
    { id: 11, title: "Final draft", dueDate: "2026-10-22", status: "todo", category: "Essay" },
    { id: 12, title: "Request recommendation", dueDate: null, status: "done", category: null },
  ],
};

afterEach(() => {
  global.fetch = originalFetch;
});

describe("deskApi parsers", () => {
  it("reduces API rows to the component shapes", () => {
    expect(toDeskTask({ id: 5, title: "x", dueDate: null, status: "in_progress" })).toEqual({
      id: "5", title: "x", dueDate: null, status: "in_progress", category: undefined,
    });
    expect(toDeskTask({ title: "no id" })).toBeNull();
    expect(toSprint(SPRINT)?.tasks).toHaveLength(2);
    expect(toSprint(null)).toBeNull();
  });

  it("leaves out units with no attempts instead of drawing them at 0%", () => {
    expect(toSkills([
      { subject: "SAT Math", unit: "Algebra", masteryPct: 94, questionsAttempted: 50 },
      { subject: "SAT Math", unit: "Geometry", masteryPct: null, questionsAttempted: 0 },
    ])).toEqual([{ subject: "SAT Math", label: "Algebra", percent: 94, attempted: 50 }]);
  });
});

describe("LiveSprintCard", () => {
  it("asks a signed-out visitor to sign in", async () => {
    global.fetch = jest.fn(async () => respond(401, { success: false, error: "Authentication required." }));
    render(<LiveSprintCard today={TODAY} />);
    expect(await screen.findByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/signin");
  });

  it("shows the current sprint, and puts a task back when the server refuses the change", async () => {
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: SPRINT }))
      .mockResolvedValueOnce(respond(503, { success: false, error: "Service unavailable." }));
    global.fetch = fetchMock;
    render(<LiveSprintCard today={TODAY} />);

    const toggle = await screen.findByRole("button", { name: "Final draft: To do" });
    fireEvent.click(toggle);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Final draft: To do" })).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/user/desk/tasks/11");
    expect(JSON.parse(init.body)).toEqual({ status: "done" });
  });

  it("offers to start a sprint when none covers today", async () => {
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: null }))
      .mockResolvedValueOnce(respond(201, { success: true, data: { ...SPRINT, tasks: [] } }));
    global.fetch = fetchMock;
    render(<LiveSprintCard today={TODAY} />);

    fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "Early Action push" } });
    fireEvent.click(screen.getByRole("button", { name: "Start sprint" }));

    await waitFor(() => expect(screen.getByText("Early Action push")).toBeInTheDocument());
    const body = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(body).toEqual({ title: "Early Action push", startDate: "2026-10-18", endDate: "2026-10-31" });
  });
});

describe("LiveSkillsCard", () => {
  it("groups units by subject and marks the weakest", async () => {
    global.fetch = jest.fn(async () => respond(200, {
      success: true,
      data: [
        { subject: "SAT Math", unit: "Algebra", masteryPct: 94, questionsAttempted: 50 },
        { subject: "SAT Math", unit: "Geometry", masteryPct: 58, questionsAttempted: 40 },
        { subject: "IELTS", unit: "Reading", masteryPct: 81, questionsAttempted: 30 },
      ],
    }));
    render(<LiveSkillsCard />);
    expect(await screen.findByText("SAT Math mastery")).toBeInTheDocument();
    expect(screen.getByText("IELTS mastery")).toBeInTheDocument();
    expect(screen.getByText("Geometry").closest("span")).toHaveTextContent(/focus next/i);
  });

  it("says so when there are no results yet", async () => {
    global.fetch = jest.fn(async () => respond(200, { success: true, data: [] }));
    render(<LiveSkillsCard />);
    expect(await screen.findByText(/No practice results yet/)).toBeInTheDocument();
  });
});
