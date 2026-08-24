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
 *
 * <p>That ownership split is also why the two list queries below read
 * different tables. A pair still awaiting a verdict is described by the live
 * mapping row; a decided one no longer is, because applying the decision is
 * precisely what rewrites that row. See {@link #findDecided(int)}.
 */
@Repository
public class MappingReviewRepository {

    /**
     * The undecided queue, read from the live mapping table.
     *
     * <p>Only ever use this for pairs the pipeline has not yet acted on: the
     * match_method filter is what makes it a review queue, and applying a
     * decision moves the row out of that filter for good.
     */
    private static final String CANDIDATE_SELECT = """
            SELECT
                m.ranking_source_id,
                rs.source_code,
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
                r.decision AS existing_decision,
                -- An undecided pair has no verdict, so it has no decision
                -- target. Selected as literal nulls to keep one row shape, and
                -- one row mapper, across both list queries.
                CAST(NULL AS BIGINT) AS decided_canonical_university_id,
                CAST(NULL AS TEXT) AS decided_canonical_name
            FROM warehouse.source_university_mapping m
            JOIN warehouse.ranking_source rs
                ON rs.ranking_source_id = m.ranking_source_id
            JOIN warehouse.canonical_university cu
                ON cu.canonical_university_id = m.canonical_university_id
            LEFT JOIN warehouse.countries c
                ON c.country_id = cu.country_id
            LEFT JOIN warehouse.mapping_review r
                ON r.ranking_source_id = m.ranking_source_id
               AND r.source_entity_id = m.source_entity_id
            WHERE m.is_active
              AND m.match_method IN ('fuzzy', 'fuzzy_review')
            """;

    /**
     * The decided list, read from warehouse.mapping_review.
     *
     * <p>Driven from the review table because the mapping row a decision was
     * made about does not survive that decision being applied: a rejection
     * retires the row (is_active = FALSE) and a confirm or remap rewrites
     * match_method to human_confirmed / human_remapped. Both outcomes fall
     * outside the queue filter in CANDIDATE_SELECT, so filtering the mapping
     * table for decided pairs can only ever return nothing.
     *
     * <p>The reviewed_* columns exist for exactly this: they are the verbatim
     * snapshot of what the reviewer was looking at, and they outlive the
     * pipeline rewriting the mapping row. The live row is still joined, but
     * only for the ancillary resolver signals the snapshot does not carry
     * (source country, token overlap, the two warning flags). Those come from
     * the most recent run rather than from review time, and are simply absent
     * when the mapping row is gone.
     */
    private static final String DECIDED_SELECT = """
            SELECT
                r.ranking_source_id,
                rs.source_code,
                r.source_entity_id,
                r.reviewed_source_name AS source_name,
                m.metadata #>> '{raw_row,location}' AS source_country,
                r.reviewed_canonical_university_id AS canonical_university_id,
                cu.display_name AS matched_canonical_name,
                c.country_name AS matched_canonical_country,
                r.reviewed_match_method AS match_method,
                r.reviewed_confidence_score AS confidence_score,
                (m.metadata ->> 'token_overlap')::double precision AS token_overlap,
                (m.metadata ->> 'country_mismatch')::boolean AS country_mismatch,
                (m.metadata ->> 'suspicious_merge')::boolean AS suspicious_merge,
                (m.metadata ->> 'candidate_count_hint')::int AS candidate_count_hint,
                r.decision AS existing_decision,
                r.decided_canonical_university_id,
                dcu.display_name AS decided_canonical_name
            FROM warehouse.mapping_review r
            JOIN warehouse.ranking_source rs
                ON rs.ranking_source_id = r.ranking_source_id
            LEFT JOIN warehouse.canonical_university cu
                ON cu.canonical_university_id = r.reviewed_canonical_university_id
            LEFT JOIN warehouse.countries c
                ON c.country_id = cu.country_id
            LEFT JOIN warehouse.canonical_university dcu
                ON dcu.canonical_university_id = r.decided_canonical_university_id
            LEFT JOIN warehouse.source_university_mapping m
                ON m.ranking_source_id = r.ranking_source_id
               AND m.source_entity_id = r.source_entity_id
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

    /**
     * Pairs already decided, so a reviewer can see and revise their own calls.
     *
     * <p>Most recent first, and it lists every standing decision -- including
     * the ones whose mapping row the rejection itself retired, which are the
     * calls a reviewer is likeliest to want to revisit.
     */
    public List<MappingReviewCandidate> findDecided(int limit) {
        return jdbcTemplate.query(
                DECIDED_SELECT + """
                        ORDER BY r.decided_at DESC, r.mapping_review_id DESC
                        LIMIT ?
                        """,
                (rs, rowNum) -> mapCandidate(rs),
                limit);
    }

    public int countPending() {
        Integer count = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*)
                FROM warehouse.source_university_mapping m
                LEFT JOIN warehouse.mapping_review r
                    ON r.ranking_source_id = m.ranking_source_id
                   AND r.source_entity_id = m.source_entity_id
                WHERE m.is_active
                  AND m.match_method IN ('fuzzy', 'fuzzy_review')
                  AND r.mapping_review_id IS NULL
                """,
                Integer.class);
        return count == null ? 0 : count;
    }

    /** Standing decisions on record, however the pipeline has since rewritten their mappings. */
    public int countDecided() {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM warehouse.mapping_review",
                Integer.class);
        return count == null ? 0 : count;
    }

    public boolean mappingExists(int rankingSourceId, String sourceEntityId) {
        Integer count = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*)
                FROM warehouse.source_university_mapping
                WHERE ranking_source_id = ? AND source_entity_id = ?
                """,
                Integer.class,
                rankingSourceId,
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
     * describes what the resolver actually produced. A re-decision deliberately
     * leaves them alone: by then the mapping row describes the applied
     * decision, not the resolver's guess, and it is the guess that the original
     * call was made against.
     */
    public int saveDecision(
            int rankingSourceId,
            String sourceEntityId,
            String decision,
            Long decidedCanonicalUniversityId,
            String decidedBy,
            String note) {
        return jdbcTemplate.update(
                """
                INSERT INTO warehouse.mapping_review (
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
                    m.ranking_source_id,
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
                FROM warehouse.source_university_mapping m
                WHERE m.ranking_source_id = ? AND m.source_entity_id = ?
                ON CONFLICT (ranking_source_id, source_entity_id)
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
                rankingSourceId,
                sourceEntityId);
    }

    private MappingReviewCandidate mapCandidate(java.sql.ResultSet rs) throws java.sql.SQLException {
        Double tokenOverlap = (Double) rs.getObject("token_overlap");
        Boolean countryMismatch = (Boolean) rs.getObject("country_mismatch");
        Boolean suspiciousMerge = (Boolean) rs.getObject("suspicious_merge");
        Integer candidateCountHint = (Integer) rs.getObject("candidate_count_hint");
        java.math.BigDecimal confidence = rs.getBigDecimal("confidence_score");

        return new MappingReviewCandidate(
                rs.getInt("ranking_source_id"),
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
                rs.getString("existing_decision"),
                (Long) rs.getObject("decided_canonical_university_id"),
                rs.getString("decided_canonical_name"));
    }
}
