import { fireEvent, render, screen, within } from "@testing-library/react";
import { CollegeListPanel } from "@/app/desk/CollegeListPanel";
import { toTarget } from "@/lib/deskApi";

const originalFetch = global.fetch;

function respond(status: number, body: unknown) {
  return { ok: status < 400, status, json: async () => body } as Response;
}

const NORTHWESTERN = {
  id: 44, name: "Northwestern University", canonicalUniversityId: 2001, universityStatus: "active", customName: null,
  programmeName: "Journalism", stage: "shortlisted", applicationRound: null, userBand: "reach", deadline: "2027-01-02",
  notes: null, createdBy: "user",
};

afterEach(() => {
  global.fetch = originalFetch;
});

describe("toTarget", () => {
  it("reads the fields the editor needs", () => {
    expect(toTarget(NORTHWESTERN)).toEqual({
      id: 44, name: "Northwestern University", stage: "shortlisted", deadline: "2027-01-02", programmeName: "Journalism",
      applicationRound: null, userBand: "reach", notes: null, linked: true, universityStatus: "active",
    });
  });
});

describe("CollegeListPanel", () => {
  it("opens a school, sends only what changed, and tells the desk", async () => {
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: [NORTHWESTERN] }))
      .mockResolvedValueOnce(respond(200, {
        success: true,
        data: { ...NORTHWESTERN, applicationRound: "RD", notes: "Medill journalism; studio courses." },
      }));
    global.fetch = fetchMock;
    const onChanged = jest.fn();
    render(<CollegeListPanel onChanged={onChanged} />);

    fireEvent.click(await screen.findByRole("button", { name: /Northwestern University/ }));
    const form = screen.getByRole("form", { name: "Edit Northwestern University" });
    expect(within(form).getByRole("button", { name: "Save" })).toBeDisabled();

    fireEvent.change(within(form).getByLabelText("Round"), { target: { value: "RD" } });
    fireEvent.change(within(form).getByLabelText(/^Notes/), { target: { value: "  Medill journalism; studio courses.  " } });
    fireEvent.click(within(form).getByRole("button", { name: "Save" }));

    expect(await within(form).findByRole("status")).toHaveTextContent("Saved.");
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/user/desk/targets/44");
    expect(init.method).toBe("PATCH");
    // Stage, deadline and label were untouched, so they are not in the PATCH.
    expect(JSON.parse(init.body)).toEqual({ applicationRound: "RD", notes: "Medill journalism; studio courses." });
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Notes ✓")).toBeInTheDocument();
  });

  it("sends the school's revision, and on a conflict loads the stored row and keeps what was typed", async () => {
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: [{ ...NORTHWESTERN, revision: 2 }] }))
      .mockResolvedValueOnce(respond(409, { success: false, error: "This is at revision 3, not 2." }))
      .mockResolvedValueOnce(respond(200, { success: true, data: [{ ...NORTHWESTERN, stage: "applying", revision: 3 }] }))
      .mockResolvedValueOnce(respond(200, {
        success: true, data: { ...NORTHWESTERN, stage: "applying", notes: "Visit in spring", revision: 4 },
      }));
    global.fetch = fetchMock;
    render(<CollegeListPanel />);
    fireEvent.click(await screen.findByRole("button", { name: /Northwestern University/ }));
    const form = screen.getByRole("form", { name: "Edit Northwestern University" });

    fireEvent.change(within(form).getByLabelText(/^Notes/), { target: { value: "Visit in spring" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent(/changed elsewhere/);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ notes: "Visit in spring", expectedRevision: 2 });
    expect(fetchMock.mock.calls[2][0]).toBe("/api/user/desk/targets");

    // Saving again sends only the typed edit, against the revision just loaded.
    fireEvent.click(within(form).getByRole("button", { name: "Save" }));
    expect(await within(form).findByRole("status")).toHaveTextContent("Saved.");
    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toEqual({ notes: "Visit in spring", expectedRevision: 3 });
  });

  it("clears a field by sending null", async () => {
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: [{ ...NORTHWESTERN, applicationRound: "EA" }] }))
      .mockResolvedValueOnce(respond(200, { success: true, data: { ...NORTHWESTERN, applicationRound: null } }));
    global.fetch = fetchMock;
    render(<CollegeListPanel />);
    fireEvent.click(await screen.findByRole("button", { name: /Northwestern University/ }));
    const form = screen.getByRole("form", { name: "Edit Northwestern University" });
    fireEvent.change(within(form).getByLabelText("Round"), { target: { value: "" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save" }));
    await within(form).findByRole("status");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ applicationRound: null });
  });

  it("shows the API's reason when a save is refused", async () => {
    global.fetch = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: [NORTHWESTERN] }))
      .mockResolvedValueOnce(respond(400, { success: false, error: "notes must be 4000 characters or fewer." }));
    render(<CollegeListPanel />);
    fireEvent.click(await screen.findByRole("button", { name: /Northwestern University/ }));
    const form = screen.getByRole("form", { name: "Edit Northwestern University" });
    fireEvent.change(within(form).getByLabelText(/^Notes/), { target: { value: "x" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("notes must be 4000 characters or fewer.");
  });

  it("removes a school only after a second click", async () => {
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: [NORTHWESTERN] }))
      .mockResolvedValueOnce(respond(200, { success: true, data: { deleted: true } }));
    global.fetch = fetchMock;
    const onChanged = jest.fn();
    render(<CollegeListPanel onChanged={onChanged} />);
    fireEvent.click(await screen.findByRole("button", { name: /Northwestern University/ }));
    fireEvent.click(screen.getByRole("button", { name: "Remove…" }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Remove Northwestern University" }));
    expect(await screen.findByText("Your schools (0)")).toBeInTheDocument();
    expect(fetchMock.mock.calls[1][1].method).toBe("DELETE");
    expect(onChanged).toHaveBeenCalled();
  });

  it("adds a school and opens it for editing", async () => {
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: [] }))
      .mockResolvedValueOnce(respond(201, { success: true, data: { ...NORTHWESTERN, id: 45, name: "University of Michigan", canonicalUniversityId: null } }));
    global.fetch = fetchMock;
    render(<CollegeListPanel />);
    const add = await screen.findByRole("form", { name: "Add a school" });
    fireEvent.change(within(add).getByLabelText("School"), { target: { value: "University of Michigan" } });
    fireEvent.click(within(add).getByRole("button", { name: "Add" }));
    expect(await screen.findByRole("form", { name: "Edit University of Michigan" })).toBeInTheDocument();
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ customName: "University of Michigan" });
  });

  it("asks a signed-out visitor to sign in", async () => {
    global.fetch = jest.fn(async () => respond(401, {}));
    render(<CollegeListPanel />);
    expect(await screen.findByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/signin");
  });
});
