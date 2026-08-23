package clawer.review.repository;

import clawer.review.dto.CanonicalOption;
import clawer.review.dto.MappingReviewCandidate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Reads the fuzzy matches awaiting review, and writes the verdicts.
 *
 * <p>Writes go to warehouse.mapping_review and nowhere else. Every pipeline
 * table -- source_university_mapping, ranking_record, aggregated_rankings --
 * is off limits here: the pipeline owns them, its upserts overwrite them on
 * every run, and it is the pipeline that applies these decisions on the next
 * ingest. Editing a mapping row directly would be silently reverted.
 */
@Repository
public class MappingReviewRepository {

    /**
     * Reads warehouse.v_entity_mapping rather than
     * warehouse.source_university_mapping.
     *
     * <p>That view unions the ranking mappings with warehouse.source_mapping,
     * where non-ranking sources land, under one source_code vocabulary. A
     * university admission page is not a ranking and has no
     * ranking_source_id, but it names universities and so needs the same
     * review as any other source.
     */
    private static final String CANDIDATE_SELECT = """
            SELECT
                m.source_code,
                m.source_entity_id,
                COALESCE(
                    m.metadata #>> '{raw_row,name}',
                    m.metadata ->> 'normalized_name',
                    m.source_entity_id
                ) AS source_name,
                m.metadata #>> '{raw_row,location}' AS source_country,
                m.canonical_university_id,
                cu.display_name AS matched_canonical_name,
                c.country_name AS matched_canonical_country,
                m.match_method,
                m.confidence_score,
                (m.metadata ->> 'token_overlap')::double precision AS token_overlap,
                (m.metadata ->> 'country_mismatch')::boolean AS country_mismatch,
                (m.metadata ->> 'suspicious_merge')::boolean AS suspicious_merge,
                (m.metadata ->> 'candidate_count_hint')::int AS candidate_count_hint,
                r.decision AS existing_decision
            FROM warehouse.v_entity_mapping m
            JOIN warehouse.canonical_university cu
                ON cu.canonical_university_id = m.canonical_university_id
            LEFT JOIN warehouse.countries c
                ON c.country_id = cu.country_id
            LEFT JOIN warehouse.mapping_review r
                ON r.source_code = m.source_code
               AND r.source_entity_id = m.source_entity_id
            WHERE m.is_active
              AND m.match_method IN ('fuzzy', 'fuzzy_review')
            """;

    private final JdbcTemplate jdbcTemplate;

    public MappingReviewRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * Fuzzy matches that are still live and not yet decided.
     *
     * <p>Lowest confidence first: those are both the likeliest to be wrong and
     * the quickest to judge. Retired mappings are excluded by {@code is_active}
     * so a rejected pair does not come back round again.
     */
    public List<MappingReviewCandidate> findPending(int limit) {
        return jdbcTemplate.query(
                CANDIDATE_SELECT + """
                          AND r.mapping_review_id IS NULL
                        ORDER BY m.confidence_score ASC, m.source_entity_id ASC
                        LIMIT ?
                        """,
                (rs, rowNum) -> mapCandidate(rs),
                limit);
    }

    /** Pairs already decided, so a reviewer can see and revise their own calls. */
    public List<MappingReviewCandidate> findDecided(int limit) {
        return jdbcTemplate.query(
                CANDIDATE_SELECT + """
                          AND r.mapping_review_id IS NOT NULL
                        ORDER BY r.decided_at DESC
                        LIMIT ?
                        """,
                (rs, rowNum) -> mapCandidate(rs),
                limit);
    }

    public int countPending() {
        Integer count = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*)
                FROM warehouse.v_entity_mapping m
                LEFT JOIN warehouse.mapping_review r
                    ON r.source_code = m.source_code
                   AND r.source_entity_id = m.source_entity_id
                WHERE m.is_active
                  AND m.match_method IN ('fuzzy', 'fuzzy_review')
                  AND r.mapping_review_id IS NULL
                """,
                Integer.class);
        return count == null ? 0 : count;
    }

    public boolean mappingExists(String sourceCode, String sourceEntityId) {
        Integer count = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*)
                FROM warehouse.v_entity_mapping
                WHERE source_code = ? AND source_entity_id = ?
                """,
                Integer.class,
                sourceCode,
                sourceEntityId);
        return count != null && count > 0;
    }

    public boolean canonicalExists(long canonicalUniversityId) {
        Integer count = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*)
                FROM warehouse.canonical_university
                WHERE canonical_university_id = ?
                """,
                Integer.class,
                canonicalUniversityId);
        return count != null && count > 0;
    }

    /** Canonical universities matching a name fragment, for choosing a remap target. */
    public List<CanonicalOption> searchCanonical(String query, int limit) {
        return jdbcTemplate.query(
                """
                SELECT cu.canonical_university_id, cu.display_name, c.country_name
                FROM warehouse.canonical_university cu
                LEFT JOIN warehouse.countries c ON c.country_id = cu.country_id
                WHERE cu.display_name ILIKE ?
                ORDER BY LENGTH(cu.display_name) ASC, cu.display_name ASC
                LIMIT ?
                """,
                (rs, rowNum) -> new CanonicalOption(
                        rs.getLong("canonical_university_id"),
                        rs.getString("display_name"),
                        rs.getString("country_name")),
                "%" + query + "%",
                limit);
    }

    /**
     * Record a verdict, replacing any earlier one for the same pair.
     *
     * <p>The reviewed_* columns are copied from the live mapping row inside the
     * same statement rather than taken from the request, so the snapshot always
     * describes what the resolver actually produced.
     *
     * <p>ranking_source_id is resolved by a LEFT JOIN, not sent by the client.
     * It is a legacy column kept for one release so the source_code migration
     * stays revertible, and a non-ranking source correctly leaves it NULL.
     */
    public int saveDecision(
            String sourceCode,
            String sourceEntityId,
            String decision,
            Long decidedCanonicalUniversityId,
            String decidedBy,
            String note) {
        return jdbcTemplate.update(
                """
                INSERT INTO warehouse.mapping_review (
                    source_code,
                    ranking_source_id,
                    source_entity_id,
                    reviewed_source_name,
                    reviewed_canonical_university_id,
                    reviewed_match_method,
                    reviewed_confidence_score,
                    decision,
                    decided_canonical_university_id,
                    decided_by,
                    note
                )
                SELECT
                    m.source_code,
                    rs.ranking_source_id,
                    m.source_entity_id,
                    COALESCE(
                        m.metadata #>> '{raw_row,name}',
                        m.metadata ->> 'normalized_name',
                        m.source_entity_id
                    ),
                    m.canonical_university_id,
                    m.match_method,
                    m.confidence_score,
                    ?,
                    ?,
                    ?,
                    ?
                FROM warehouse.v_entity_mapping m
                LEFT JOIN warehouse.ranking_source rs
                    ON rs.source_code = m.source_code
                WHERE m.source_code = ? AND m.source_entity_id = ?
                ON CONFLICT (source_code, source_entity_id)
                DO UPDATE SET
                    decision = EXCLUDED.decision,
                    decided_canonical_university_id = EXCLUDED.decided_canonical_university_id,
                    decided_by = EXCLUDED.decided_by,
                    decided_at = CURRENT_TIMESTAMP,
                    note = EXCLUDED.note
                """,
                decision,
                decidedCanonicalUniversityId,
                decidedBy,
                note,
                sourceCode,
                sourceEntityId);
    }

    private MappingReviewCandidate mapCandidate(java.sql.ResultSet rs) throws java.sql.SQLException {
        Double tokenOverlap = (Double) rs.getObject("token_overlap");
        Boolean countryMismatch = (Boolean) rs.getObject("country_mismatch");
        Boolean suspiciousMerge = (Boolean) rs.getObject("suspicious_merge");
        Integer candidateCountHint = (Integer) rs.getObject("candidate_count_hint");
        java.math.BigDecimal confidence = rs.getBigDecimal("confidence_score");

        return new MappingReviewCandidate(
                rs.getString("source_code"),
                rs.getString("source_entity_id"),
                rs.getString("source_name"),
                rs.getString("source_country"),
                (Long) rs.getObject("canonical_university_id"),
                rs.getString("matched_canonical_name"),
                rs.getString("matched_canonical_country"),
                rs.getString("match_method"),
                confidence == null ? null : confidence.doubleValue(),
                tokenOverlap,
                countryMismatch,
                suspiciousMerge,
                candidateCountHint,
                rs.getString("existing_decision"));
    }
}
