package clawer.review.dto;

/**
 * One fuzzy match awaiting a human verdict.
 *
 * <p>Everything a reviewer needs to judge the pair without leaving the page:
 * what the source called it, what the resolver matched it to, and the signals
 * behind that guess. The two country fields are kept separate on purpose -- a
 * mismatch between them is the single strongest hint that the match is wrong.
 */
public record MappingReviewCandidate(
        int rankingSourceId,
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
        String existingDecision) {
}
