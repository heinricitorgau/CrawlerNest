/**
 * Shapes and wording for the entity-resolution review screen.
 *
 * The API serves one row shape for both tabs. On the pending tab the matched_*
 * fields are the resolver's live guess and the decision fields are empty; on the
 * decided tab they are the snapshot of that guess taken when the verdict was
 * recorded, and the decision fields say what the reviewer chose instead. Reading
 * them as "what was reviewed" and "what was decided" holds in both cases.
 */

export type Decision = "confirmed" | "rejected" | "remapped";

export interface ReviewCandidate {
  rankingSourceId: number;
  sourceCode: string;
  sourceEntityId: string;
  sourceName: string;
  sourceCountry: string | null;
  matchedCanonicalUniversityId: number | null;
  matchedCanonicalName: string | null;
  matchedCanonicalCountry: string | null;
  matchMethod: string;
  confidenceScore: number | null;
  tokenOverlap: number | null;
  countryMismatch: boolean | null;
  suspiciousMerge: boolean | null;
  candidateCountHint: number | null;
  existingDecision: string | null;
  // Null for a rejection as well as for an undecided pair -- a rejection names
  // no university on purpose. `existingDecision` is what tells the two apart.
  decidedCanonicalUniversityId: number | null;
  decidedCanonicalName: string | null;
}

export interface ReviewPayload {
  items: ReviewCandidate[];
  totalPending: number;
  totalDecided: number;
  caveats: string[];
}

/**
 * What a recorded verdict actually did to the pair.
 *
 * A rejection carries no university by design, so the absence of one is the
 * outcome rather than missing data, and saying so is the honest rendering --
 * "no target on record" would read as a bug in the screen. Confirm and remap
 * both name a target, and the target is the whole content of the verdict.
 */
export function decisionOutcome(candidate: ReviewCandidate): string {
  if (candidate.existingDecision === null) {
    return "not yet decided";
  }
  if (candidate.existingDecision === "rejected") {
    return "credited to no university";
  }
  if (candidate.decidedCanonicalUniversityId === null) {
    // Refused by the API, so it means the row predates that rule or was
    // written around it. Saying the target is missing beats inventing one.
    return "no target on record";
  }
  if (candidate.decidedCanonicalName === null) {
    // The university the verdict named has since gone from the warehouse.
    return `id ${candidate.decidedCanonicalUniversityId} (no longer in the warehouse)`;
  }
  return `credited to ${candidate.decidedCanonicalName} · id ${candidate.decidedCanonicalUniversityId}`;
}
