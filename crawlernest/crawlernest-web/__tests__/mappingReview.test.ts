import { decisionOutcome, type ReviewCandidate } from "@/lib/mappingReview";

function candidate(overrides: Partial<ReviewCandidate> = {}): ReviewCandidate {
  return {
    sourceCode: "QS",
    sourceEntityId: "846",
    sourceName: "NOVA University of Lisbon",
    sourceCountry: "Portugal",
    matchedCanonicalUniversityId: 260,
    matchedCanonicalName: "University of Lisbon",
    matchedCanonicalCountry: "Portugal",
    matchMethod: "fuzzy_review",
    confidenceScore: 0.82,
    tokenOverlap: 0.6,
    countryMismatch: false,
    suspiciousMerge: true,
    candidateCountHint: 4,
    existingDecision: null,
    decidedCanonicalUniversityId: null,
    decidedCanonicalName: null,
    ...overrides,
  };
}

describe("decisionOutcome", () => {
  it("says a rejection credits nobody, rather than reporting a missing target", () => {
    // A rejection names no university by design, so an empty target is the
    // verdict itself. Rendering it as absent data would read as a bug.
    expect(
      decisionOutcome(candidate({ existingDecision: "rejected" }))
    ).toBe("credited to no university");
  });

  it("names the university a remap moved the source onto", () => {
    expect(
      decisionOutcome(
        candidate({
          existingDecision: "remapped",
          decidedCanonicalUniversityId: 777,
          decidedCanonicalName: "NOVA University Lisbon",
        })
      )
    ).toBe("credited to NOVA University Lisbon · id 777");
  });

  it("names the kept university when the resolver was confirmed", () => {
    expect(
      decisionOutcome(
        candidate({
          existingDecision: "confirmed",
          decidedCanonicalUniversityId: 260,
          decidedCanonicalName: "University of Lisbon",
        })
      )
    ).toBe("credited to University of Lisbon · id 260");
  });

  it("distinguishes a target that has left the warehouse from one never recorded", () => {
    expect(
      decisionOutcome(
        candidate({ existingDecision: "confirmed", decidedCanonicalUniversityId: 260 })
      )
    ).toBe("id 260 (no longer in the warehouse)");
    expect(
      decisionOutcome(candidate({ existingDecision: "confirmed" }))
    ).toBe("no target on record");
  });

  it("reports an undecided pair as undecided", () => {
    expect(decisionOutcome(candidate())).toBe("not yet decided");
  });
});
