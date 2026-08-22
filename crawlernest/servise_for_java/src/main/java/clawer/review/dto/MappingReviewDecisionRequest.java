package clawer.review.dto;

/**
 * A reviewer's verdict on one source entity.
 *
 * <p>Only the identity of the pair and the verdict come from the client. What
 * was reviewed -- the matched university, the method, the score -- is read
 * server-side from the live mapping row, so the stored evidence cannot be
 * forged or fall out of step with what the pipeline actually did.
 */
public record MappingReviewDecisionRequest(
        String sourceCode,
        String sourceEntityId,
        String decision,
        Long decidedCanonicalUniversityId,
        String note) {
}
