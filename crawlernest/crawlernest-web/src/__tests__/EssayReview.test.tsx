import { fireEvent, render, screen, within } from "@testing-library/react";
import { EssayReviewPanel, LatestEssayCard } from "@/app/desk/EssayReviewPanel";
import { EssayReviewResult } from "@/components/desk";
import { CAVEAT_ESSAY_OVERALL_METHOD, CAVEAT_ESSAY_SCORE_ESTIMATE } from "@/lib/caveatMessages";
import { toEssayReview } from "@/lib/deskApi";

const originalFetch = global.fetch;

function respond(status: number, body: unknown) {
  return { ok: status < 400, status, json: async () => body } as Response;
}

/** As the Java EssayService returns it. */
const API_REVIEW = {
  id: 318,
  essayTitle: "Personal statement",
  draftText: "The first time the robot arm failed, I blamed the motor.",
  wordCount: 11,
  rubricVersion: "essay-rubric-2026.1",
  overall: { score: 73.8, method: "weighted_mean" },
  dimensions: [
    { key: "impact", label: "Impact", score: 82, rationale: "Concrete stakes.", evidence: [] },
    { key: "introspection", label: "Introspection", score: 64, rationale: "States the lesson.", evidence: [] },
    { key: "passion", label: "Passion", score: 78, rationale: "Time spent.", evidence: [] },
    { key: "originality", label: "Originality", score: 71, rationale: "Specific.", evidence: [] },
  ],
  suggestions: [
    { start: 0, end: 10, original: "I blamed the motor.", suggested: "I blamed the motor [for how long?].", dimension: "introspection", reason: "Show it." },
  ],
  comparedToRevision: { id: 305, overallDelta: 4.1, dimensionDeltas: { impact: 3, introspection: 9, passion: 0, originality: 2 } },
  cached: false,
  isEstimated: true,
  provenance: { model: "test-model", evaluatedAt: "2026-10-18T08:43:21Z" },
  caveats: [CAVEAT_ESSAY_SCORE_ESTIMATE, CAVEAT_ESSAY_OVERALL_METHOD],
};

afterEach(() => {
  global.fetch = originalFetch;
});

describe("toEssayReview", () => {
  it("reads the API's review", () => {
    const review = toEssayReview(API_REVIEW)!;
    expect(review.overallScore).toBe(73.8);
    expect(review.dimensions.map((d) => d.key)).toEqual(["impact", "introspection", "passion", "originality"]);
    expect(review.comparedToRevision?.overallDelta).toBe(4.1);
    expect(review.model).toBe("test-model");
  });

  it("refuses a review that does not say it is an estimate", () => {
    expect(toEssayReview({ ...API_REVIEW, isEstimated: false })).toBeNull();
    expect(toEssayReview({ ...API_REVIEW, isEstimated: undefined })).toBeNull();
  });
});

describe("EssayReviewResult", () => {
  it("shows the caveats beside the scores, and the before and after", () => {
    render(<EssayReviewResult review={toEssayReview(API_REVIEW)!} />);
    expect(screen.getByText(CAVEAT_ESSAY_SCORE_ESTIMATE)).toBeInTheDocument();
    expect(screen.getByText(CAVEAT_ESSAY_OVERALL_METHOD)).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Overall (estimate)" })).toHaveAttribute("aria-valuenow", "73.8");
    const revisions = screen.getByRole("region", { name: "Suggested revisions" });
    expect(within(revisions).getByText("I blamed the motor.")).toBeInTheDocument();
    expect(within(revisions).getByText("I blamed the motor [for how long?].")).toBeInTheDocument();
    expect(screen.getByText("+9")).toBeInTheDocument();
  });

  it("keeps the caveats in its compact form too", () => {
    render(<EssayReviewResult review={toEssayReview(API_REVIEW)!} compact />);
    expect(screen.getByText(CAVEAT_ESSAY_SCORE_ESTIMATE)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Suggested revisions" })).toBeNull();
  });
});

describe("EssayReviewPanel", () => {
  it("shows the API's own reason when no model is configured", async () => {
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: [] }))
      .mockResolvedValueOnce(respond(503, {
        success: false, code: "MODEL_UNAVAILABLE",
        error: "No model is configured, so this cannot run. Nothing was stored.",
      }));
    global.fetch = fetchMock;
    render(<EssayReviewPanel />);

    fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "Personal statement" } });
    fireEvent.change(screen.getByLabelText("Draft"), { target: { value: "  My draft, with its leading spaces." } });
    fireEvent.click(screen.getByRole("button", { name: "Score draft" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No model is configured");
    // The draft goes as typed: offsets are into exactly that text.
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).draftText).toBe("  My draft, with its leading spaces.");
  });

  it("shows the review once scored", async () => {
    global.fetch = jest.fn()
      .mockResolvedValueOnce(respond(200, { success: true, data: [] }))
      .mockResolvedValueOnce(respond(200, { success: true, data: API_REVIEW }));
    render(<EssayReviewPanel />);
    fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "Personal statement" } });
    fireEvent.change(screen.getByLabelText("Draft"), { target: { value: "The first time the robot arm failed." } });
    fireEvent.click(screen.getByRole("button", { name: "Score draft" }));
    expect(await screen.findByText("Suggested revisions")).toBeInTheDocument();
    expect(screen.getByText("Earlier reviews")).toBeInTheDocument();
  });
});

describe("LatestEssayCard", () => {
  it("points to the Essay review tab when nothing is scored yet", async () => {
    global.fetch = jest.fn(async () => respond(200, { success: true, data: [] }));
    const open = jest.fn();
    render(<LatestEssayCard onOpenReviews={open} />);
    fireEvent.click(await screen.findByRole("button", { name: "Open essay review" }));
    expect(open).toHaveBeenCalled();
    expect(screen.getByText("No drafts scored yet")).toBeInTheDocument();
  });
});

describe("word limit", () => {
  it("shows words against the limit and flags going over", () => {
    render(<EssayReviewResult review={{ ...toEssayReview(API_REVIEW)!, wordCount: 672, wordLimit: 650 }} compact />);
    expect(screen.getByText("672 of 650 words · 22 over")).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Words against the limit" })).toHaveAttribute("aria-valuenow", "672");
  });

  it("reads the limit from the API, null when none was given", () => {
    expect(toEssayReview({ ...API_REVIEW, wordLimit: 650 })!.wordLimit).toBe(650);
    expect(toEssayReview(API_REVIEW)!.wordLimit).toBeNull();
  });
});
