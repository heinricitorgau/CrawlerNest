import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { LiveDeadlinesCard, LiveSkillsCard, LiveSprintCard } from "@/app/desk/LiveDeskCards";
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
    ])).toEqual([{ subject: "SAT Math", label: "Algebra", percent: 94, attempted: 50, correct: 0 }]);
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

  it("sends the task's revision, keeps the server's row, and reloads when the task changed elsewhere", async () => {
    const withRevisions = { ...SPRINT, tasks: SPRINT.tasks.map((t, i) => ({ ...t, revision: 4 + i })) };
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: withRevisions }))
      .mockResolvedValueOnce(respond(200, { success: true, data: { ...withRevisions.tasks[0], status: "done", revision: 5 } }))
      .mockResolvedValueOnce(respond(409, { success: false, error: "This is at revision 6, not 5." }))
      .mockResolvedValueOnce(respond(200, {
        success: true,
        data: { ...withRevisions, tasks: [{ ...withRevisions.tasks[0], title: "Final draft (v2)", status: "done", revision: 6 }, withRevisions.tasks[1]] },
      }));
    global.fetch = fetchMock;
    render(<LiveSprintCard today={TODAY} />);

    fireEvent.click(await screen.findByRole("button", { name: "Final draft: To do" }));
    // A second tick while the first save is in flight is ignored, not sent with the old revision.
    fireEvent.click(screen.getByRole("button", { name: "Final draft: Done" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Final draft: Done" })).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ status: "done", expectedRevision: 4 });
    await act(async () => {}); // let the save settle

    // The next tick carries the revision the first save returned.
    fireEvent.click(screen.getByRole("button", { name: "Final draft: Done" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/changed elsewhere/);
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ status: "todo", expectedRevision: 5 });

    // ...and the stored sprint replaces the stale one.
    expect(await screen.findByRole("button", { name: "Final draft (v2): Done" })).toBeInTheDocument();
    expect(fetchMock.mock.calls[3][0]).toBe("/api/user/desk/sprints/current");
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

describe("LiveSkillsCard practice and overall", () => {
  it("pools the overall over questions, not units, and logs practice for the focus unit", async () => {
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(respond(200, {
        success: true,
        data: [
          { subject: "SAT Math", unit: "Algebra", masteryPct: 90, questionsAttempted: 200, questionsCorrect: 180 },
          { subject: "SAT Math", unit: "Geometry", masteryPct: 40, questionsAttempted: 5, questionsCorrect: 2 },
        ],
      }))
      .mockResolvedValueOnce(respond(200, {
        success: true,
        data: { subject: "SAT Math", unit: "Geometry", masteryPct: 60, questionsAttempted: 15, questionsCorrect: 9 },
      }));
    global.fetch = fetchMock;
    render(<LiveSkillsCard />);

    // 182 of 205, not the mean of 90% and 40%.
    expect(await screen.findByText("88.8% of 205 questions")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Log practice →" }));
    const form = screen.getByRole("form", { name: "Record practice result" });
    expect(within(form).getByLabelText("Unit")).toHaveValue("Geometry");
    fireEvent.change(within(form).getByLabelText("Questions"), { target: { value: "10" } });
    fireEvent.change(within(form).getByLabelText("Correct"), { target: { value: "7" } });
    fireEvent.click(within(form).getByRole("button", { name: "Record result" }));

    // The server returns the unit's new totals (15 / 9): 189 of 215 overall.
    expect(await screen.findByText("87.9% of 215 questions")).toBeInTheDocument();
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ subject: "SAT Math", unit: "Geometry", attempted: 10, correct: 7 });
  });

  it("will not send more correct answers than questions", async () => {
    global.fetch = jest.fn(async () => respond(200, { success: true, data: [] }));
    render(<LiveSkillsCard />);
    const form = await screen.findByRole("form", { name: "Record practice result" });
    fireEvent.change(within(form).getByLabelText("Subject"), { target: { value: "SAT Math" } });
    fireEvent.change(within(form).getByLabelText("Unit"), { target: { value: "Algebra" } });
    fireEvent.change(within(form).getByLabelText("Questions"), { target: { value: "5" } });
    fireEvent.change(within(form).getByLabelText("Correct"), { target: { value: "6" } });
    expect(within(form).getByRole("button", { name: "Record result" })).toBeDisabled();
    expect(within(form).getByText("Correct cannot exceed questions.")).toBeInTheDocument();
  });
});

describe("LiveDeadlinesCard", () => {
  it("lists upcoming deadlines of schools still in play, soonest first", async () => {
    global.fetch = jest.fn(async () => respond(200, {
      success: true,
      data: [
        { id: 1, name: "Northwestern University", stage: "applying", deadline: "2026-11-01", programmeName: null },
        { id: 2, name: "University of Michigan", stage: "shortlisted", deadline: "2026-10-25", programmeName: "Computer Science" },
        { id: 3, name: "Already submitted", stage: "submitted", deadline: "2026-10-20", programmeName: null },
        { id: 4, name: "Past deadline", stage: "applying", deadline: "2026-10-01", programmeName: null },
        { id: 5, name: "No deadline", stage: "applying", deadline: null, programmeName: null },
      ],
    }));
    render(<LiveDeadlinesCard today={TODAY} />);
    const list = await screen.findByRole("list", { name: "Application deadlines" });
    const names = within(list).getAllByRole("listitem").map((li) => li.querySelector("p")?.textContent);
    expect(names).toEqual(["University of Michigan", "Northwestern University"]);
    expect(within(list).getByText("Oct 25 · 7d")).toBeInTheDocument();
  });

  it("says nothing to a signed-out visitor; the sprint card already does", async () => {
    global.fetch = jest.fn(async () => respond(401, {}));
    const { container } = render(<LiveDeadlinesCard today={TODAY} />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
