package clawer.repository;

import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.ScopedRankedUniversity;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * Covers the entry requirements that {@link JdbcScopedRankingReadAdapter} attaches
 * to recommendation candidates.
 *
 * <p>This path used to join {@code warehouse.admission_requirements}, which holds
 * a row per university with every requirement column NULL, so {@code ielts_min}
 * came back null for all 1499 of them and no test noticed. Reading the structured
 * columns on {@code warehouse.admission_record} is what makes these assertions
 * possible at all.
 */
@SpringBootTest
@SqlGroup({
        @Sql(
                scripts = {
                        "classpath:sql/rankings_integration_setup.sql",
                        "classpath:sql/rankings_integration_seed.sql"
                },
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD
        ),
        @Sql(
                scripts = "classpath:sql/rankings_integration_cleanup.sql",
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD
        )
})
class ScopedRankingAdmissionIntegrationTest {

    private static final long ETH_ZURICH = 990001L;
    private static final long MIT = 990002L;

    @Autowired
    private JdbcScopedRankingReadAdapter adapter;

    private List<ScopedRankedUniversity> candidates() {
        return adapter.findRecommendationCandidates(RankingContext.fromQuery("global", null), 2099, null);
    }

    private ScopedRankedUniversity candidate(long canonicalUniversityId) {
        Optional<ScopedRankedUniversity> match = candidates().stream()
                .filter(row -> row.getCanonicalUniversityId() != null
                        && row.getCanonicalUniversityId() == canonicalUniversityId)
                .findFirst();
        return match.orElseThrow(() ->
                new AssertionError("no recommendation candidate for canonical university " + canonicalUniversityId));
    }

    @Test
    void candidatesAreProducedAtAll() {
        assertFalse(candidates().isEmpty(), "fixture should yield recommendation candidates");
    }

    @Test
    void carriesEveryStructuredRequirementOntoTheCandidate() {
        ScopedRankedUniversity row = candidate(ETH_ZURICH);

        assertEquals(7.0, row.getIeltsMin());
        assertEquals(100, row.getToeflMin());
        assertEquals(120, row.getDuolingoMin());
        assertEquals(3.5, row.getGpaMin());
        assertEquals("2099-01-15", row.getApplicationDeadline());
    }

    @Test
    void leavesUnpublishedRequirementsNull() {
        ScopedRankedUniversity row = candidate(MIT);

        // The fixture publishes only IELTS and TOEFL for this one. A card that
        // rendered 0 for the rest would claim there is no GPA bar and no deadline.
        assertEquals(7.5, row.getIeltsMin());
        assertEquals(105, row.getToeflMin());
        assertNull(row.getDuolingoMin());
        assertNull(row.getGpaMin());
        assertNull(row.getApplicationDeadline());
    }
}
