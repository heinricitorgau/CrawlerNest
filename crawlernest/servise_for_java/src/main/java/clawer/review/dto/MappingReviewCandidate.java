package clawer.review.dto;

/**
 * One source-to-canonical pair on the review screen.
 *
 * <p>Everything a reviewer needs to judge the pair without leaving the page:
 * what the source called it, what the resolver matched it to, and the signals
 * behind that guess. The two country fields are kept separate on purpose -- a
 * mismatch between them is the single strongest hint that the match is wrong.
 *
 * <p>The pair is identified by sourceCode, not by a ranking source id: a
 * source that is not a ranking has no such id, and reviewing it is the same
 * job either way.
 *
 * <p>The same shape carries both lists. On the pending list the matched_* and
 * match_method fields are the resolver's live guess and the decision fields are
 * null; on the decided list they are the snapshot of that guess taken when the
 * verdict was recorded, and the decision fields say what the reviewer chose
 * instead. Reading them as "what was reviewed" and "what was decided" holds in
 * both cases.
 *
 * <p>{@code decidedCanonicalUniversityId} is null for a rejection as well as
 * for an undecided pair: a rejection deliberately names no university. Tell the
 * two apart by {@code existingDecision}, not by this field.
 */
public record MappingReviewCandidate(
        String sourceCode,
        String sourceEntityId,
        String sourceName,
        String sourceCountry,
        Long matchedCanonicalUniversityId,
        String matchedCanonicalName,
        String matchedCanonicalCountry,
        String matchMethod,
        Double confidenceScore,
        Double tokenOverlap,
        Boolean countryMismatch,
        Boolean suspiciousMerge,
        Integer candidateCountHint,
        String existingDecision,
        Long decidedCanonicalUniversityId,
        String decidedCanonicalName) {
}
