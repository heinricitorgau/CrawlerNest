import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ConversationHistoryPanel } from "@/components/ConversationHistoryPanel";
import {
  deleteConversation,
  getConversationById,
  getConversations,
  type ConversationApiResult,
  type ConversationDetail,
  type ConversationSummary,
} from "@/lib/conversationsApi";

jest.mock("@/lib/conversationsApi", () => ({
  getConversations: jest.fn(),
  getConversationById: jest.fn(),
  deleteConversation: jest.fn(),
}));

const mockedList = getConversations as jest.MockedFunction<typeof getConversations>;
const mockedById = getConversationById as jest.MockedFunction<typeof getConversationById>;
const mockedDelete = deleteConversation as jest.MockedFunction<typeof deleteConversation>;

function summary(overrides: Partial<ConversationSummary> = {}): ConversationSummary {
  return {
    id: 1,
    sessionId: "session-1",
    title: "How rankings work",
    turnCount: 2,
    preview: "How is the aggregated rank computed?",
    createdAt: "2026-08-25T01:00:00Z",
    updatedAt: "2026-08-25T02:00:00Z",
    ...overrides,
  };
}

function detail(overrides: Partial<ConversationDetail> = {}): ConversationDetail {
  return {
    id: 1,
    sessionId: "session-1",
    title: "How rankings work",
    turns: [
      { role: "user", content: "A question" },
      { role: "assistant", content: "An answer" },
    ],
    createdAt: "2026-08-25T01:00:00Z",
    updatedAt: "2026-08-25T02:00:00Z",
    ...overrides,
  };
}

/** A promise the test resolves by hand, to hold a request in flight. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

function renderPanel(props: Partial<React.ComponentProps<typeof ConversationHistoryPanel>> = {}) {
  const onClose = jest.fn();
  const onLoad = jest.fn();
  const onSessionExpired = jest.fn();
  render(
    <ConversationHistoryPanel
      onClose={onClose}
      onLoad={onLoad}
      onSessionExpired={onSessionExpired}
      {...props}
    />
  );
  return { onClose, onLoad, onSessionExpired };
}

beforeEach(() => {
  jest.clearAllMocks();
  mockedList.mockResolvedValue({ ok: true, data: [summary()] });
  mockedById.mockResolvedValue({ ok: true, data: detail() });
  mockedDelete.mockResolvedValue({ ok: true, data: null });
});

describe("ConversationHistoryPanel: listing", () => {
  it("fetches once on mount and renders the row", async () => {
    renderPanel();

    expect(await screen.findByText("How rankings work")).toBeInTheDocument();
    expect(mockedList).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/2 turns/)).toBeInTheDocument();
    expect(screen.getByText("How is the aggregated rank computed?")).toBeInTheDocument();
  });

  it("says so when nothing has been saved yet", async () => {
    mockedList.mockResolvedValue({ ok: true, data: [] });
    renderPanel();

    expect(await screen.findByText(/have not saved a conversation yet/i)).toBeInTheDocument();
  });

  it("offers a retry after a backend outage", async () => {
    mockedList.mockResolvedValueOnce({
      ok: false,
      reason: "unavailable",
      message: "Service unavailable. Please try again later.",
    });
    renderPanel();

    expect(await screen.findByText("Service unavailable. Please try again later.")).toBeInTheDocument();

    mockedList.mockResolvedValueOnce({ ok: true, data: [summary()] });
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("How rankings work")).toBeInTheDocument();
  });

  it("tells the page when the session has expired", async () => {
    mockedList.mockResolvedValue({
      ok: false,
      reason: "unauthenticated",
      message: "Your session has expired. Please sign in again.",
    });
    const { onSessionExpired } = renderPanel();

    expect(await screen.findByText(/session has expired/i)).toBeInTheDocument();
    // An outage offers a retry; this needs a sign-in, so the page has to know.
    expect(onSessionExpired).toHaveBeenCalled();
  });

  it("marks the conversation already on screen", async () => {
    mockedList.mockResolvedValue({
      ok: true,
      data: [summary({ id: 1, sessionId: "session-1" }), summary({ id: 2, sessionId: "session-2" })],
    });
    renderPanel({ activeSessionId: "session-2" });

    expect(await screen.findByText("On screen")).toBeInTheDocument();
  });
});

describe("ConversationHistoryPanel: loading a transcript", () => {
  it("hands the transcript to the page and closes", async () => {
    const { onLoad, onClose } = renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Load" }));

    await waitFor(() => expect(onLoad).toHaveBeenCalledTimes(1));
    expect(onLoad).toHaveBeenCalledWith(detail());
    expect(onClose).toHaveBeenCalled();
  });

  it("shows progress and locks every row while the request is in flight", async () => {
    mockedList.mockResolvedValue({ ok: true, data: [summary({ id: 1 }), summary({ id: 2, title: "Second" })] });
    const pending = deferred<ConversationApiResult<ConversationDetail>>();
    mockedById.mockReturnValue(pending.promise);

    renderPanel();
    const loadButtons = await screen.findAllByRole("button", { name: "Load" });
    fireEvent.click(loadButtons[0]);

    expect(await screen.findByRole("button", { name: "Loading…" })).toBeDisabled();
    // The other row locks too: otherwise its Delete could remove a row while
    // this one is still being opened.
    const stillLoad = screen.getByRole("button", { name: "Load" });
    expect(stillLoad).toBeDisabled();
    screen.getAllByRole("button", { name: /^Delete / }).forEach((button) => {
      expect(button).toBeDisabled();
    });

    pending.resolve({ ok: true, data: detail() });
    await waitFor(() => expect(mockedById).toHaveBeenCalledTimes(1));
  });

  it("ignores a second click while one load is already running", async () => {
    const pending = deferred<ConversationApiResult<ConversationDetail>>();
    mockedById.mockReturnValue(pending.promise);

    renderPanel();
    const load = await screen.findByRole("button", { name: "Load" });
    fireEvent.click(load);
    fireEvent.click(load);
    fireEvent.click(load);

    pending.resolve({ ok: true, data: detail() });
    await waitFor(() => expect(mockedById).toHaveBeenCalledTimes(1));
  });

  it("drops a row that was deleted elsewhere and refetches", async () => {
    mockedById.mockResolvedValue({
      ok: false,
      reason: "not_found",
      message: "Not found.",
    });
    const { onLoad } = renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Load" }));

    expect(await screen.findByText("That conversation is no longer available.")).toBeInTheDocument();
    expect(onLoad).not.toHaveBeenCalled();
    // Refetched, so the stale row does not linger in the list.
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(2));
  });

  it("keeps the panel open when the transcript cannot be fetched", async () => {
    mockedById.mockResolvedValue({
      ok: false,
      reason: "unavailable",
      message: "Service unavailable. Please try again later.",
    });
    const { onClose, onLoad } = renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Load" }));

    expect(await screen.findByText("Service unavailable. Please try again later.")).toBeInTheDocument();
    expect(onLoad).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("ConversationHistoryPanel: deleting", () => {
  it("removes the row without refetching the whole list", async () => {
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: /^Delete / }));

    await waitFor(() => expect(screen.queryByText("How rankings work")).not.toBeInTheDocument());
    expect(mockedDelete).toHaveBeenCalledWith(1);
    // One fetch, from mount: refetching would flash the whole list for one row.
    expect(mockedList).toHaveBeenCalledTimes(1);
  });

  it("shows progress and locks every row while deleting", async () => {
    const pending = deferred<ConversationApiResult<null>>();
    mockedDelete.mockReturnValue(pending.promise);

    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: /^Delete / }));

    expect(await screen.findByRole("button", { name: "Deleting…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Load" })).toBeDisabled();

    pending.resolve({ ok: true, data: null });
    await waitFor(() => expect(mockedDelete).toHaveBeenCalledTimes(1));
  });

  it("ignores a second click while one delete is already running", async () => {
    const pending = deferred<ConversationApiResult<null>>();
    mockedDelete.mockReturnValue(pending.promise);

    renderPanel();
    const del = await screen.findByRole("button", { name: /^Delete / });
    fireEvent.click(del);
    fireEvent.click(del);

    pending.resolve({ ok: true, data: null });
    await waitFor(() => expect(mockedDelete).toHaveBeenCalledTimes(1));
  });

  it("treats an already-deleted row as success", async () => {
    mockedDelete.mockResolvedValue({
      ok: false,
      reason: "not_found",
      message: "Not found.",
    });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: /^Delete / }));

    // Gone is gone: surfacing an error for a row that is already absent would
    // ask the user to react to nothing.
    await waitFor(() => expect(screen.queryByText("How rankings work")).not.toBeInTheDocument());
  });

  it("keeps the row and explains when the delete fails", async () => {
    mockedDelete.mockResolvedValue({
      ok: false,
      reason: "unavailable",
      message: "Service unavailable. Please try again later.",
    });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: /^Delete / }));

    expect(await screen.findByText("Service unavailable. Please try again later.")).toBeInTheDocument();
    expect(screen.getByText("How rankings work")).toBeInTheDocument();
  });
});

describe("ConversationHistoryPanel: dismissing", () => {
  it("closes on the Close button", async () => {
    const { onClose } = renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalled();
  });

  it("closes on Escape", async () => {
    const { onClose } = renderPanel();
    await screen.findByText("How rankings work");

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalled();
  });

  it("does not close on a click inside the dialog", async () => {
    const { onClose } = renderPanel();

    fireEvent.click(await screen.findByRole("dialog"));

    expect(onClose).not.toHaveBeenCalled();
  });
});
