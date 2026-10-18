import { fireEvent, render, screen } from "@testing-library/react";
import { LiveNarrativeCard } from "@/app/desk/LiveNarrativeCard";
import { CAVEAT_NARRATIVE_ESTIMATE, CAVEAT_RESONANCE_GENERAL_KNOWLEDGE } from "@/lib/caveatMessages";
import { toNarrative } from "@/lib/deskApi";

const originalFetch = global.fetch;

function respond(status: number, body: unknown) {
  return { ok: status < 400, status, json: async () => body } as Response;
}

const theme = (status: string) => ({
  id: 17, title: "The Builder Who Teaches", summary: "You build, then you teach.", traits: ["Maker", "Mentor"], status,
  evidence: [{ kind: "essay_review", refId: "318", quote: "I rebuilt the arm three times." }],
  isEstimated: true, provenance: { model: "test-model" },
});

const EMPTY = { themes: [], resonance: [], caveats: [CAVEAT_NARRATIVE_ESTIMATE] };
const SUGGESTED = { themes: [theme("suggested")], resonance: [], caveats: [CAVEAT_NARRATIVE_ESTIMATE] };
const ACCEPTED_WITH_FIT = {
  themes: [theme("accepted")],
  resonance: [
    { themeId: 17, targetEntityId: 41, institution: "Notes College", level: 5, rationale: "Your notes fit.", institutionBasis: "user_notes", isEstimated: true },
    { themeId: 17, targetEntityId: 47, institution: "Quiet University", level: 2, rationale: "Little link.", institutionBasis: "model_general_knowledge", isEstimated: true },
  ],
  caveats: [CAVEAT_NARRATIVE_ESTIMATE, CAVEAT_RESONANCE_GENERAL_KNOWLEDGE],
};

afterEach(() => {
  global.fetch = originalFetch;
});

describe("toNarrative", () => {
  it("drops any row that does not carry isEstimated", () => {
    const n = toNarrative({
      themes: [theme("accepted"), { ...theme("accepted"), id: 18, isEstimated: undefined }],
      resonance: [{ ...ACCEPTED_WITH_FIT.resonance[0], isEstimated: false }],
      caveats: [],
    });
    expect(n.themes.map((t) => t.id)).toEqual([17]);
    expect(n.resonance).toEqual([]);
  });
});

describe("LiveNarrativeCard", () => {
  it("finds themes, then keeps one", async () => {
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: EMPTY }))
      .mockResolvedValueOnce(respond(200, { success: true, data: SUGGESTED }))
      .mockResolvedValueOnce(respond(200, { success: true, data: { ...SUGGESTED, themes: [theme("accepted")] } }));
    global.fetch = fetchMock;
    render(<LiveNarrativeCard />);

    fireEvent.click(await screen.findByRole("button", { name: "Find my themes" }));
    expect(await screen.findByText("Suggested")).toBeInTheDocument();
    expect(screen.getByText("“I rebuilt the arm three times.”")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Keep this theme" }));
    expect(await screen.findByRole("button", { name: "Assess fit with my schools" })).toBeInTheDocument();
    expect(screen.queryByText("Suggested")).toBeNull();
    const [url, init] = fetchMock.mock.calls[2];
    expect(url).toBe("/api/user/desk/story/themes/17");
    expect(JSON.parse(init.body)).toEqual({ status: "accepted" });
  });

  it("shows each fit as a level with where the school side came from, and the caveats", async () => {
    global.fetch = jest.fn(async () => respond(200, { success: true, data: ACCEPTED_WITH_FIT }));
    render(<LiveNarrativeCard />);
    const strong = await screen.findByRole("meter", { name: "The Builder Who Teaches resonance with Notes College" });
    expect(strong).toHaveAttribute("aria-valuetext", "Strong, level 5 of 5");
    expect(screen.getByText("Your notes fit. (From your notes.)")).toBeInTheDocument();
    expect(screen.getByText("Little link. (From the model's general knowledge.)")).toBeInTheDocument();
    expect(screen.getByText(CAVEAT_NARRATIVE_ESTIMATE)).toBeInTheDocument();
    expect(screen.getByText(CAVEAT_RESONANCE_GENERAL_KNOWLEDGE)).toBeInTheDocument();
  });

  it("shows the API's reason when there is nothing to draw themes from", async () => {
    global.fetch = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: EMPTY }))
      .mockResolvedValueOnce(respond(400, { success: false, error: "Have at least one essay draft reviewed first: themes are drawn from your own writing." }));
    render(<LiveNarrativeCard />);
    fireEvent.click(await screen.findByRole("button", { name: "Find my themes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Have at least one essay draft reviewed first");
  });
});
