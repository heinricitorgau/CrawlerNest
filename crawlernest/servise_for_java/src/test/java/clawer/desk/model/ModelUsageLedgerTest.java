package clawer.desk.model;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.time.Duration;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;
import org.springframework.transaction.support.TransactionTemplate;

/** desk.model_call against PostgreSQL: what counts, what is summed, and that a rolled-back caller keeps its row. */
@SpringBootTest
@TestPropertySource(properties = "crawlernest.jwt.secret=an-integration-test-secret-long-enough-for-hs256")
@SqlGroup({
        @Sql(scripts = {"classpath:sql/desk_integration_setup.sql", "classpath:sql/desk_integration_seed.sql"},
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD),
        @Sql(scripts = "classpath:sql/desk_integration_cleanup.sql",
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD)
})
class ModelUsageLedgerTest {

    private static final long USER = 990401L;

    @Autowired
    private ModelUsageLedger ledger;

    @Autowired
    private JdbcTemplate jdbc;

    @Autowired
    private TransactionTemplate tx;

    @Test
    void countsWhatTheProviderAnsweredAndSumsOnlyReportedTokens() {
        ledger.record(USER, "/e", "m", ModelUsageLedger.Outcome.OK, 100, 20);
        ledger.record(USER, "/e", "m", ModelUsageLedger.Outcome.OK, null, null);
        ledger.record(USER, "/e", "m", ModelUsageLedger.Outcome.PROVIDER_ERROR, 5, 5);
        ledger.record(USER, "/e", "m", ModelUsageLedger.Outcome.UNREACHABLE, null, null);

        assertEquals(3, ledger.countedCallTimes(USER, Duration.ofDays(1)).size());
        Map<String, Object> summary = ledger.summary(USER, Duration.ofDays(1));
        assertEquals(3L, summary.get("modelCalls"));
        assertEquals(1L, summary.get("unreachableCalls"));
        assertEquals(100L, summary.get("promptTokens"));
        assertEquals(20L, summary.get("completionTokens"));
        assertEquals(1L, summary.get("callsWithoutUsage"));
        // A provider error's token figures are dropped, never stored.
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM desk.model_call WHERE user_id = ? "
                + "AND outcome = 'provider_error' AND prompt_tokens IS NOT NULL", Integer.class, USER));
    }

    @Test
    void aCallInsideATransactionThatRollsBackStillCounts() {
        assertThrows(IllegalStateException.class, () -> tx.executeWithoutResult(status -> {
            ledger.record(USER, "/e", "m", ModelUsageLedger.Outcome.OK, 1, 1);
            throw new IllegalStateException("the reply was unusable; the service stores nothing");
        }));
        assertEquals(1, ledger.countedCallTimes(USER, Duration.ofDays(1)).size());
    }

    @Test
    void theTableRefusesTokensOnACallThatWasNotAnswered() {
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO desk.model_call (user_id, endpoint, outcome, prompt_tokens) VALUES (?, '/e', 'unreachable', 3)",
                USER));
    }

    @Test
    void aCallOutsideTheWindowNoLongerCounts() {
        jdbc.update("INSERT INTO desk.model_call (user_id, endpoint, outcome, called_at) "
                + "VALUES (?, '/e', 'ok', now() - interval '25 hours')", USER);
        assertEquals(0, ledger.countedCallTimes(USER, Duration.ofDays(1)).size());
    }
}
