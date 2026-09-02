package clawer.review.repository;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Guards the one thing that made the decided tab permanently empty.
 *
 * <p>The two lists have to read different tables. A decision is applied by the
 * pipeline rewriting the mapping row it was made about -- a rejection retires
 * it, a confirm or remap rewrites match_method to human_* -- so the queue's own
 * filter excludes, by construction, every pair that has ever been decided.
 * Building the decided list out of that filter can only ever return nothing,
 * which is exactly what it used to do.
 *
 * <p>Asserted against the SQL rather than a database because the bug was not a
 * wrong result from a right query: the query returned precisely what it asked
 * for, and what it asked for was the empty set. A fixture would have to
 * reproduce a whole pipeline run to say anything the statement does not.
 */
class MappingReviewRepositoryTest {

    private RecordingJdbcTemplate jdbcTemplate;
    private MappingReviewRepository repository;

    @BeforeEach
    void setUp() {
        jdbcTemplate = new RecordingJdbcTemplate();
        repository = new MappingReviewRepository(jdbcTemplate);
    }

    @Test
    void thePendingQueueReadsTheLiveMappingView() {
        repository.findPending(25);

        assertTrue(jdbcTemplate.lastSql.contains("FROM warehouse.v_entity_mapping m"));
        assertTrue(jdbcTemplate.lastSql.contains("m.match_method IN ('fuzzy', 'fuzzy_review')"));
        assertTrue(jdbcTemplate.lastSql.contains("r.mapping_review_id IS NULL"));
        assertArrayEquals(new Object[] {25}, jdbcTemplate.lastArgs);
    }

    @Test
    void theDecidedListIsDrivenFromTheReviewTable() {
        repository.findDecided(25);

        assertTrue(jdbcTemplate.lastSql.contains("FROM warehouse.mapping_review r"));
        assertTrue(jdbcTemplate.lastSql.contains("ORDER BY r.decided_at DESC"));
        assertArrayEquals(new Object[] {25}, jdbcTemplate.lastArgs);
    }

    @Test
    void theDecidedListDoesNotApplyTheQueueFilter() {
        // Both halves of the filter exclude every decided pair: the rewritten
        // match_method fails the IN, and a rejection fails is_active.
        repository.findDecided(25);

        assertFalse(jdbcTemplate.lastSql.contains("match_method IN ('fuzzy', 'fuzzy_review')"));
        assertFalse(jdbcTemplate.lastSql.contains("WHERE m.is_active"));
        assertFalse(jdbcTemplate.lastSql.contains("mapping_review_id IS NOT NULL"));
    }

    @Test
    void theDecidedListNeverInnerJoinsTheMappingView() {
        // A rejection retires the mapping row, so the decided list has to
        // survive its absence. Counted rather than matched against a literal
        // with whitespace in it, which reformatting would break.
        repository.findDecided(25);
        String sql = jdbcTemplate.lastSql;

        assertTrue(sql.contains("LEFT JOIN warehouse.v_entity_mapping m"));
        assertEquals(
                countOccurrences(sql, "JOIN warehouse.v_entity_mapping"),
                countOccurrences(sql, "LEFT JOIN warehouse.v_entity_mapping"),
                "every join onto the mapping view must be a LEFT join");
    }

    @Test
    void theDecidedListCarriesTheEvidenceThatOutlivesTheMappingRow() {
        // The reviewed_* snapshot, not the live row, is what the reviewer was
        // looking at; the live row is joined only for the ancillary signals.
        repository.findDecided(25);

        assertTrue(jdbcTemplate.lastSql.contains("r.reviewed_source_name"));
        assertTrue(jdbcTemplate.lastSql.contains("r.reviewed_canonical_university_id"));
        assertTrue(jdbcTemplate.lastSql.contains("r.reviewed_match_method"));
        assertTrue(jdbcTemplate.lastSql.contains("r.reviewed_confidence_score"));
    }

    @Test
    void everyColumnTheRowMapperReadsIsSelectedByBothLists() {
        // One row mapper serves both statements, so a column present in only
        // one of them fails at runtime rather than at compile time. Names, not
        // positions: both lists alias their expressions to these.
        List<String> mapped = List.of(
                "source_code",
                "source_entity_id",
                "source_name",
                "source_country",
                "canonical_university_id",
                "matched_canonical_name",
                "matched_canonical_country",
                "match_method",
                "confidence_score",
                "token_overlap",
                "country_mismatch",
                "suspicious_merge",
                "candidate_count_hint",
                "existing_decision",
                "decided_canonical_university_id",
                "decided_canonical_name");

        repository.findPending(25);
        String pending = jdbcTemplate.lastSql;
        repository.findDecided(25);
        String decided = jdbcTemplate.lastSql;

        for (String column : mapped) {
            assertTrue(pending.contains(column), "pending list omits " + column);
            assertTrue(decided.contains(column), "decided list omits " + column);
        }
    }

    private static int countOccurrences(String haystack, String needle) {
        int count = 0;
        for (int i = haystack.indexOf(needle); i >= 0; i = haystack.indexOf(needle, i + 1)) {
            count++;
        }
        return count;
    }

    /**
     * Captures the statement instead of running it. The repository builds its
     * SQL by string concatenation, so what it hands to JdbcTemplate is the
     * whole of its behaviour here.
     */
    private static final class RecordingJdbcTemplate extends JdbcTemplate {

        private String lastSql;
        private Object[] lastArgs;

        @Override
        public <T> List<T> query(String sql, RowMapper<T> rowMapper, Object... args) {
            this.lastSql = sql;
            this.lastArgs = args;
            return List.of();
        }
    }
}
