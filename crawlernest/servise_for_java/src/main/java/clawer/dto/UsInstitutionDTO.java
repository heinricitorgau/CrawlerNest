package clawer.dto;

import java.math.BigDecimal;
import java.util.List;

/**
 * US federal institutional data for one university (College Scorecard, IPEDS).
 *
 * <p>Not ranking data: none of it is part of a rank, composite score or confidence
 * label. Every value carries its own {@code referencePeriod} -- an admission rate is
 * for one fall, earnings for a cohort that entered a decade earlier -- and its
 * {@code status}. A value whose status is not {@code reported} or {@code imputed}
 * has no {@code value}, and is not zero.
 */
public record UsInstitutionDTO(
        Long canonicalUniversityId,
        Integer unitid,
        String institutionName,
        String city,
        String stateCode,
        String website,
        String matchMethod,
        String wikidataId,
        List<Source> sources,
        List<Metric> metrics,
        List<String> caveats
) {
    /** Who published the figures, for the attribution line. */
    public record Source(String code, String name, String publisher, String url, String license) {}

    public record Metric(
            String source,
            String key,
            String sourceField,
            String unit,
            BigDecimal value,
            String valueText,
            String status,
            String statusDetail,
            String referencePeriod,
            String release
    ) {}
}
