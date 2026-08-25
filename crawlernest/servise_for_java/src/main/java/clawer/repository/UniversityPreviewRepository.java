package clawer.repository;

import clawer.dto.AdmissionPreviewSummaryDTO;
import clawer.dto.CanonicalUniversityDetailPreviewDTO;
import clawer.dto.DataAvailabilityDTO;
import clawer.dto.IdentitySummaryDTO;
import clawer.dto.RankingPreviewSummaryDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.Array;
import java.sql.Timestamp;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Optional;

@Repository
public class UniversityPreviewRepository {
    private final JdbcTemplate jdbcTemplate;

    public UniversityPreviewRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Optional<CanonicalUniversityDetailPreviewDTO> findByCanonicalUniversityId(Long canonicalUniversityId) {
        return resolveIdentityByCanonicalUniversityId(canonicalUniversityId)
                .map(this::buildDetailPreview);
    }

    public Optional<CanonicalUniversityDetailPreviewDTO> findByUniversityName(String universityName) {
        return resolveIdentityByUniversityName(universityName)
                .map(this::buildDetailPreview);
    }

    private Optional<IdentityLookupRow> resolveIdentityByCanonicalUniversityId(Long canonicalUniversityId) {
        if (canonicalUniversityId == null) {
            return Optional.empty();
        }
        List<IdentityLookupRow> rows = jdbcTemplate.query(
                """
                SELECT
                    cu.canonical_university_id,
                    cu.display_name,
                    cu.display_name_normalized,
                    cu.canonical_slug,
                    cu.status,
                    cu.country_id,
                    cu.city_name,
                    cu.website_url,
                    'canonicalUniversityId' AS matched_by,
                    CAST(cu.canonical_university_id AS TEXT) AS matched_value
                FROM warehouse.canonical_university cu
                WHERE cu.canonical_university_id = ?
                LIMIT 1
                """,
                (rs, rowNum) -> new IdentityLookupRow(
                        rs.getLong("canonical_university_id"),
                        rs.getString("display_name"),
                        rs.getString("display_name_normalized"),
                        rs.getString("canonical_slug"),
                        rs.getString("status"),
                        (Integer) rs.getObject("country_id"),
                        rs.getString("city_name"),
                        rs.getString("website_url"),
                        rs.getString("matched_by"),
                        rs.getString("matched_value")
                ),
                canonicalUniversityId
        );
        return rows.stream().findFirst();
    }

    private Optional<IdentityLookupRow> resolveIdentityByUniversityName(String universityName) {
        String lookupName = universityName == null ? "" : universityName.trim();
        if (lookupName.isEmpty()) {
            return Optional.empty();
        }
        String normalizedLookup = normalizeUniversityName(lookupName);

        List<IdentityLookupRow> normalizedRows = jdbcTemplate.query(
                """
                SELECT
                    cu.canonical_university_id,
                    cu.display_name,
                    cu.display_name_normalized,
                    cu.canonical_slug,
                    cu.status,
                    cu.country_id,
                    cu.city_name,
                    cu.website_url,
                    'displayNameNormalized' AS matched_by,
                    cu.display_name_normalized AS matched_value
                FROM warehouse.canonical_university cu
                WHERE LOWER(cu.display_name_normalized) = LOWER(?)
                ORDER BY
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM warehouse.ranking_record rr
                            WHERE rr.canonical_university_id = cu.canonical_university_id
                        ) OR EXISTS (
                            SELECT 1
                            FROM warehouse.admission_record arp
                            WHERE arp.canonical_university_id = cu.canonical_university_id
                        ) THEN 0
                        ELSE 1
                    END ASC,
                    cu.canonical_university_id ASC
                LIMIT 1
                """,
                identityLookupRowMapper(),
                normalizedLookup
        );
        if (!normalizedRows.isEmpty()) {
            return Optional.of(normalizedRows.get(0));
        }

        List<IdentityLookupRow> displayRows = jdbcTemplate.query(
                """
                SELECT
                    cu.canonical_university_id,
                    cu.display_name,
                    cu.display_name_normalized,
                    cu.canonical_slug,
                    cu.status,
                    cu.country_id,
                    cu.city_name,
                    cu.website_url,
                    'displayName' AS matched_by,
                    cu.display_name AS matched_value
                FROM warehouse.canonical_university cu
                WHERE LOWER(cu.display_name) = LOWER(?)
                ORDER BY
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM warehouse.ranking_record rr
                            WHERE rr.canonical_university_id = cu.canonical_university_id
                        ) OR EXISTS (
                            SELECT 1
                            FROM warehouse.admission_record arp
                            WHERE arp.canonical_university_id = cu.canonical_university_id
                        ) THEN 0
                        ELSE 1
                    END ASC,
                    cu.canonical_university_id ASC
                LIMIT 1
                """,
                identityLookupRowMapper(),
                lookupName
        );
        if (!displayRows.isEmpty()) {
            return Optional.of(displayRows.get(0));
        }

        List<IdentityLookupRow> aliasNormalizedRows = jdbcTemplate.query(
                """
                SELECT
                    cu.canonical_university_id,
                    cu.display_name,
                    cu.display_name_normalized,
                    cu.canonical_slug,
                    cu.status,
                    cu.country_id,
                    cu.city_name,
                    cu.website_url,
                    'aliasNormalized' AS matched_by,
                    ua.alias_normalized AS matched_value
                FROM warehouse.university_alias ua
                JOIN warehouse.canonical_university cu
                  ON cu.canonical_university_id = ua.canonical_university_id
                WHERE LOWER(ua.alias_normalized) = LOWER(?)
                ORDER BY
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM warehouse.ranking_record rr
                            WHERE rr.canonical_university_id = cu.canonical_university_id
                        ) OR EXISTS (
                            SELECT 1
                            FROM warehouse.admission_record arp
                            WHERE arp.canonical_university_id = cu.canonical_university_id
                        ) THEN 0
                        ELSE 1
                    END ASC,
                    cu.canonical_university_id ASC,
                    ua.alias_id ASC
                LIMIT 1
                """,
                identityLookupRowMapper(),
                normalizedLookup
        );
        if (!aliasNormalizedRows.isEmpty()) {
            return Optional.of(aliasNormalizedRows.get(0));
        }

        List<IdentityLookupRow> aliasTextRows = jdbcTemplate.query(
                """
                SELECT
                    cu.canonical_university_id,
                    cu.display_name,
                    cu.display_name_normalized,
                    cu.canonical_slug,
                    cu.status,
                    cu.country_id,
                    cu.city_name,
                    cu.website_url,
                    'aliasText' AS matched_by,
                    ua.alias_text AS matched_value
                FROM warehouse.university_alias ua
                JOIN warehouse.canonical_university cu
                  ON cu.canonical_university_id = ua.canonical_university_id
                WHERE LOWER(ua.alias_text) = LOWER(?)
                ORDER BY
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM warehouse.ranking_record rr
                            WHERE rr.canonical_university_id = cu.canonical_university_id
                        ) OR EXISTS (
                            SELECT 1
                            FROM warehouse.admission_record arp
                            WHERE arp.canonical_university_id = cu.canonical_university_id
                        ) THEN 0
                        ELSE 1
                    END ASC,
                    cu.canonical_university_id ASC,
                    ua.alias_id ASC
                LIMIT 1
                """,
                identityLookupRowMapper(),
                lookupName
        );
        return aliasTextRows.stream().findFirst();
    }

    private org.springframework.jdbc.core.RowMapper<IdentityLookupRow> identityLookupRowMapper() {
        return (rs, rowNum) -> new IdentityLookupRow(
                rs.getLong("canonical_university_id"),
                rs.getString("display_name"),
                rs.getString("display_name_normalized"),
                rs.getString("canonical_slug"),
                rs.getString("status"),
                (Integer) rs.getObject("country_id"),
                rs.getString("city_name"),
                rs.getString("website_url"),
                rs.getString("matched_by"),
                rs.getString("matched_value")
        );
    }

    private CanonicalUniversityDetailPreviewDTO buildDetailPreview(IdentityLookupRow identity) {
        List<String> aliases = jdbcTemplate.query(
                """
                SELECT alias_text
                FROM warehouse.university_alias
                WHERE canonical_university_id = ?
                ORDER BY is_primary DESC, is_abbreviation DESC, alias_text ASC
                """,
                (rs, rowNum) -> rs.getString("alias_text"),
                identity.canonicalUniversityId()
        );

        RankingPreviewSummaryDTO rankingSummary = jdbcTemplate.queryForObject(
                """
                WITH ranking_rows AS (
                    SELECT
                        src.source_code AS source,
                        rr.ranking_year,
                        rr.rank_position
                    FROM warehouse.ranking_record rr
                    JOIN warehouse.ranking_source src
                      ON src.ranking_source_id = rr.ranking_source_id
                    WHERE rr.canonical_university_id = ?
                ),
                ranking_summary AS (
                    SELECT
                        COUNT(*)::INTEGER AS row_count,
                        COUNT(DISTINCT source)::INTEGER AS source_count,
                        ARRAY_AGG(DISTINCT source ORDER BY source) AS sources,
                        ARRAY_AGG(DISTINCT ranking_year ORDER BY ranking_year) AS ranking_years,
                        MIN(rank_position)::INTEGER AS best_rank
                    FROM ranking_rows
                ),
                -- rank_position is nullable on ranking_record (the preview table
                -- it replaced had rank NOT NULL), so an unranked row must not
                -- win the best-rank slot and hand back a best_source with a
                -- null best_rank beside it.
                ranking_best AS (
                    SELECT source, ranking_year
                    FROM ranking_rows
                    WHERE rank_position IS NOT NULL
                    ORDER BY rank_position ASC, ranking_year DESC, source ASC
                    LIMIT 1
                )
                SELECT
                    rs.row_count,
                    rs.source_count,
                    rs.sources,
                    rs.ranking_years,
                    rs.best_rank,
                    rb.source AS best_source,
                    rb.ranking_year AS best_ranking_year
                FROM ranking_summary rs
                LEFT JOIN ranking_best rb ON TRUE
                """,
                (rs, rowNum) -> {
                    int rowCount = rs.getInt("row_count");
                    if (rowCount <= 0) {
                        return null;
                    }
                    RankingPreviewSummaryDTO dto = new RankingPreviewSummaryDTO();
                    dto.setRowCount(rowCount);
                    dto.setSourceCount(rs.getInt("source_count"));
                    dto.setSources(stringArray(rs.getArray("sources")));
                    dto.setRankingYears(integerArray(rs.getArray("ranking_years")));
                    dto.setBestRank((Integer) rs.getObject("best_rank"));
                    dto.setBestSource(rs.getString("best_source"));
                    dto.setBestRankingYear((Integer) rs.getObject("best_ranking_year"));
                    return dto;
                },
                identity.canonicalUniversityId()
        );

        AdmissionPreviewSummaryDTO admissionSummary = jdbcTemplate.queryForObject(
                """
                SELECT
                    COUNT(*)::INTEGER AS row_count,
                    COUNT(DISTINCT source_url)::INTEGER AS source_url_count,
                    ARRAY_REMOVE(ARRAY_AGG(DISTINCT country ORDER BY country), NULL) AS countries,
                    MIN(ielts_requirement) AS best_ielts_requirement,
                    MIN(toefl_requirement)::INTEGER AS best_toefl_requirement,
                    MAX(extracted_at) AS latest_extracted_at
                FROM warehouse.admission_record
                WHERE canonical_university_id = ?
                """,
                (rs, rowNum) -> {
                    int rowCount = rs.getInt("row_count");
                    if (rowCount <= 0) {
                        return null;
                    }
                    AdmissionPreviewSummaryDTO dto = new AdmissionPreviewSummaryDTO();
                    dto.setRowCount(rowCount);
                    dto.setSourceUrlCount(rs.getInt("source_url_count"));
                    dto.setCountries(stringArray(rs.getArray("countries")));
                    dto.setBestIeltsRequirement((Double) rs.getObject("best_ielts_requirement"));
                    dto.setBestToeflRequirement((Integer) rs.getObject("best_toefl_requirement"));
                    Timestamp latestExtractedAt = rs.getTimestamp("latest_extracted_at");
                    dto.setLatestExtractedAt(
                            latestExtractedAt == null ? null : latestExtractedAt.toInstant().toString()
                    );
                    return dto;
                },
                identity.canonicalUniversityId()
        );

        List<String> missingSections = new ArrayList<>();
        if (rankingSummary == null) {
            missingSections.add("rankingSummary");
        }
        if (admissionSummary == null) {
            missingSections.add("admissionSummary");
        }

        DataAvailabilityDTO dataAvailability = new DataAvailabilityDTO();
        dataAvailability.setHasRankingData(rankingSummary != null);
        dataAvailability.setHasAdmissionData(admissionSummary != null);
        dataAvailability.setMissingSections(missingSections);

        IdentitySummaryDTO identitySummary = new IdentitySummaryDTO();
        identitySummary.setCanonicalSlug(identity.canonicalSlug());
        identitySummary.setStatus(identity.status());
        identitySummary.setAliasCount(aliases.size());
        identitySummary.setCountryId(identity.countryId());
        identitySummary.setCityName(identity.cityName());
        identitySummary.setWebsiteUrl(identity.websiteUrl());
        identitySummary.setMatchedBy(identity.matchedBy());
        identitySummary.setMatchedValue(identity.matchedValue());

        CanonicalUniversityDetailPreviewDTO dto = new CanonicalUniversityDetailPreviewDTO();
        dto.setCanonicalUniversityId(identity.canonicalUniversityId());
        dto.setUniversityDisplayName(identity.displayName());
        dto.setNormalizedUniversityName(identity.displayNameNormalized());
        dto.setAliases(aliases);
        dto.setIdentitySummary(identitySummary);
        dto.setRankingSummary(rankingSummary);
        dto.setAdmissionSummary(admissionSummary);
        dto.setDataAvailability(dataAvailability);
        return dto;
    }

    private static String normalizeUniversityName(String value) {
        String trimmed = value == null ? "" : value.trim().replaceAll("\\s+", " ");
        if (trimmed.isEmpty()) {
            return trimmed;
        }
        String[] tokens = trimmed.split(" ");
        List<String> normalizedTokens = new ArrayList<>();
        for (String token : tokens) {
            if (token.equals(token.toUpperCase(Locale.ROOT)) && token.length() <= 5) {
                normalizedTokens.add(token);
            } else if (token.equals(token.toLowerCase(Locale.ROOT)) || token.equals(token.toUpperCase(Locale.ROOT))) {
                normalizedTokens.add(token.substring(0, 1).toUpperCase(Locale.ROOT) + token.substring(1).toLowerCase(Locale.ROOT));
            } else {
                normalizedTokens.add(token);
            }
        }
        return String.join(" ", normalizedTokens);
    }

    private static List<String> stringArray(Array sqlArray) {
        if (sqlArray == null) {
            return List.of();
        }
        try {
            Object array = sqlArray.getArray();
            if (array instanceof String[] values) {
                return Arrays.asList(values);
            }
            if (array instanceof Object[] objects) {
                return Arrays.stream(objects).map(String::valueOf).toList();
            }
            return List.of();
        } catch (Exception ex) {
            return List.of();
        }
    }

    private static List<Integer> integerArray(Array sqlArray) {
        if (sqlArray == null) {
            return List.of();
        }
        try {
            Object array = sqlArray.getArray();
            if (array instanceof Integer[] values) {
                return Arrays.asList(values);
            }
            if (array instanceof Object[] objects) {
                return Arrays.stream(objects)
                        .map(value -> value == null ? null : Integer.valueOf(String.valueOf(value)))
                        .filter(value -> value != null)
                        .toList();
            }
            return List.of();
        } catch (Exception ex) {
            return List.of();
        }
    }

    private record IdentityLookupRow(
            Long canonicalUniversityId,
            String displayName,
            String displayNameNormalized,
            String canonicalSlug,
            String status,
            Integer countryId,
            String cityName,
            String websiteUrl,
            String matchedBy,
            String matchedValue
    ) {}
}
