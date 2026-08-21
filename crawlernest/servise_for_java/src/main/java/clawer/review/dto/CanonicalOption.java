package clawer.review.dto;

/** A canonical university offered as a remap target. */
public record CanonicalOption(
        long canonicalUniversityId,
        String displayName,
        String country) {
}
