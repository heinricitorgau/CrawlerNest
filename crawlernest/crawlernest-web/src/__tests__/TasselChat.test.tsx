import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import DeskPage from "@/app/desk/page";
import { ActionCard } from "@/components/desk";
import { toChatAction } from "@/lib/deskApi";
import { CAVEAT_US_FEDERAL_PERIODS, CAVEAT_US_FEDERAL_SOURCE } from "@/lib/caveatMessages";

const originalFetch = global.fetch;

function respond(status: number, body: unknown) {
  return { ok: status < 400, status, json: async () => body } as Response;
}

/** Every desk card reads an empty desk; the chat and action routes answer as given. */
function routedFetch(chat: (body: Record<string, unknown>) => Response, decide?: (url: string) => Response) {
  return jest.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/user/desk/chat/message") return chat(JSON.parse(String(init?.body)));
    if (url.startsWith("/api/user/desk/chat/actions/") && decide) return decide(url);
    if (url === "/api/user/desk/story/narrative") return respond(200, { success: true, data: { themes: [], resonance: [], caveats: [] } });
    if (url === "/api/user/desk/sprints/current") return respond(200, { success: true, data: null });
    return respond(200, { success: true, data: [] });
  }) as unknown as jest.Mock;
}

const APPLIED = { id: "a1", tool: "create_action_task", status: "applied", message: "Added the task \"Send SAT scores\", due 2026-10-25." };
const PROPOSED = { id: "a2", tool: "update_target_list", status: "proposed", message: "Proposed to update Northwestern. It waits for the user to confirm it on the desk." };

afterEach(() => {
  global.fetch = originalFetch;
});

describe("toChatAction", () => {
  it("keeps only known statuses", () => {
    expect(toChatAction(APPLIED)).toEqual(APPLIED);
    expect(toChatAction({ ...APPLIED, status: "done-ish" })).toBeNull();
  });
});

describe("ActionCard", () => {
  it("offers undo for an applied change and confirm or reject for a proposal", () => {
    const { rerender } = render(<ActionCard action={toChatAction(APPLIED)!} onDecide={jest.fn()} />);
    expect(screen.getByText("Task · Done")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
    rerender(<ActionCard action={toChatAction(PROPOSED)!} onDecide={jest.fn()} />);
    expect(screen.getByText("School list · Waiting for you")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("shows a failed call as not having happened, with nothing to press", () => {
    render(<ActionCard action={{ id: "a3", tool: "create_action_task", status: "failed", message: "The due date is in the past." }} onDecide={jest.fn()} />);
    expect(screen.getByText("Task · Didn't happen")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("Tassel on /desk", () => {
  it("sends the message with history and mode, shows the changes, and re-reads the desk", async () => {
    const fetchMock = routedFetch(() => respond(200, {
      success: true,
      data: { reply: { text: "Added it to your tasks." }, actions: [APPLIED], disclosure: { model: "m" } },
    }));
    global.fetch = fetchMock;
    render(<DeskPage />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/user/desk/sprints/current", expect.anything()));
    const sprintReads = () => fetchMock.mock.calls.filter(([url]) => url === "/api/user/desk/sprints/current").length;
    const before = sprintReads();

    fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: "Send my SAT scores by the 25th" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Added it to your tasks.")).toBeInTheDocument();
    const changes = screen.getByLabelText("Changes from this reply");
    expect(within(changes).getByText("Task · Done")).toBeInTheDocument();
    const sent = JSON.parse(fetchMock.mock.calls.find(([url]) => url === "/api/user/desk/chat/message")![1].body);
    expect(sent).toMatchObject({ message: "Send my SAT scores by the 25th", history: [], mode: "general" });
    expect(typeof sent.sessionId).toBe("string");
    await waitFor(() => expect(sprintReads()).toBeGreaterThan(before));
  });

  it("shows the caveats of the figures Tassel read under its reply, and no change card for a read", async () => {
    const fetchMock = routedFetch(() => respond(200, {
      success: true,
      data: {
        reply: { text: "Its admission rate was 4.6% in Fall 2024." }, actions: [],
        caveats: [CAVEAT_US_FEDERAL_SOURCE, CAVEAT_US_FEDERAL_PERIODS, ""],
        disclosure: { model: "m", warehouseReads: [{ tool: "lookup_us_federal_data", status: "found", unitid: 166683 }] },
      },
    }));
    global.fetch = fetchMock;
    render(<DeskPage />);
    fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: "How selective is MIT?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Its admission rate was 4.6% in Fall 2024.")).toBeInTheDocument();
    const note = screen.getByRole("note", { name: "About the figures in this reply" });
    expect(within(note).getByText(CAVEAT_US_FEDERAL_SOURCE)).toBeInTheDocument();
    expect(within(note).getByText(CAVEAT_US_FEDERAL_PERIODS)).toBeInTheDocument();
    expect(within(note).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.queryByLabelText("Changes from this reply")).not.toBeInTheDocument();
  });

  it("shows no caveat box when the reply read nothing", async () => {
    global.fetch = routedFetch(() => respond(200, { success: true, data: { reply: { text: "Hello!" }, actions: [] } }));
    render(<DeskPage />);
    fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Hello!")).toBeInTheDocument();
    expect(screen.queryByRole("note", { name: "About the figures in this reply" })).not.toBeInTheDocument();
  });

  it("confirms a proposal through the action route", async () => {
    const fetchMock = routedFetch(
      () => respond(200, { success: true, data: { reply: { text: "Confirm it below." }, actions: [PROPOSED] } }),
      () => respond(200, { success: true, data: { id: "a2", tool: "update_target_list", status: "confirmed" } }),
    );
    global.fetch = fetchMock;
    render(<DeskPage />);
    fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: "Move Northwestern to RD" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm" }));
    expect(await screen.findByText("School list · Confirmed")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/user/desk/chat/actions/a2/confirm", expect.objectContaining({ method: "POST" }));
  });

  it("asks a signed-out visitor to sign in", async () => {
    global.fetch = routedFetch(() => respond(401, {}));
    render(<DeskPage />);
    fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Sign in to talk to Tassel.")).toBeInTheDocument();
  });
});
