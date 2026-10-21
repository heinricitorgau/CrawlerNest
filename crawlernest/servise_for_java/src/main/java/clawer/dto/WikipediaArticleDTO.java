package clawer.dto;

import java.util.List;

/**
 * The Wikipedia article matched to a university, as the university page shows it.
 *
 * <p>The text is Wikipedia's, under {@code license}: a client that renders
 * {@code sections} must show {@code pageUrl} and the licence beside it. It is not
 * warehouse data. An article may quote a rank from an edition the warehouse does
 * not hold, which is why {@code notice} travels with the text rather than being
 * left to each client to word.
 */
public record WikipediaArticleDTO(
        Long canonicalUniversityId,
        String language,
        String wikidataId,
        String pageTitle,
        String pageUrl,
        Long revisionId,
        String revisionUrl,
        String revisionTimestamp,
        String matchMethod,
        String license,
        String licenseUrl,
        String fetchedAt,
        String notice,
        List<Section> sections
) {
    /** One section of the article. The lead comes first, with level 1 and a null heading. */
    public record Section(int level, String heading, String text) {}
}
