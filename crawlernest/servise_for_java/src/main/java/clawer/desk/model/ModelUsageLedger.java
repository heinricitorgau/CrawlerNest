package clawer.desk.model;

import java.sql.Timestamp;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * desk.model_call (V010): every call this API makes to the model, and what the day's budget is counted from.
 *
 * <p>Writing a row never fails the request that made the call: the model has already answered, and a reply the user
 * cannot see because bookkeeping failed would be the worse outcome. A failed write is logged, and that call goes
 * uncounted.
 *
 * <p>The row is written in its own transaction. A model call can happen inside a service's transaction that later
 * rolls back (an unusable reply stores nothing); the call was still made and must still count.
 */
@Component
public class ModelUsageLedger {

    public enum Outcome {
        OK("ok"), PROVIDER_ERROR("provider_error"), UNREACHABLE("unreachable");

        final String column;

        Outcome(String column) {
            this.column = column;
        }
    }

    /** The calls that count against the budget: the provider answered, whatever it answered. */
    private static final String COUNTED = "outcome IN ('ok', 'provider_error')";

    private static final Logger log = LoggerFactory.getLogger(ModelUsageLedger.class);

    private final JdbcTemplate jdbc;
    private final Clock clock;
    private final TransactionTemplate ownTransaction;

    @Autowired
    public ModelUsageLedger(JdbcTemplate jdbc, PlatformTransactionManager transactions) {
        this(jdbc, transactions, Clock.systemUTC());
    }

    public ModelUsageLedger(JdbcTemplate jdbc, PlatformTransactionManager transactions, Clock clock) {
        this.jdbc = jdbc;
        this.clock = clock;
        this.ownTransaction = new TransactionTemplate(transactions);
        this.ownTransaction.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    }

    public void record(Long userId, String endpoint, String modelName, Outcome outcome,
                       Integer promptTokens, Integer completionTokens) {
        try {
            ownTransaction.executeWithoutResult(status -> jdbc.update("""
                    INSERT INTO desk.model_call
                        (user_id, endpoint, model_name, outcome, prompt_tokens, completion_tokens, called_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, userId, truncate(endpoint, 120), truncate(modelName, 200), outcome.column,
                    outcome == Outcome.OK ? promptTokens : null, outcome == Outcome.OK ? completionTokens : null,
                    Timestamp.from(clock.instant())));
        } catch (DataAccessException e) {
            log.warn("Could not record a model call for user {} on {}: {}", userId, endpoint, e.getMessage());
        }
    }

    /** When each counted call in the last {@code window} was made, oldest first. */
    public List<Instant> countedCallTimes(long userId, Duration window) {
        return jdbc.query("SELECT called_at FROM desk.model_call WHERE user_id = ? AND called_at > ? AND " + COUNTED
                        + " ORDER BY called_at",
                (rs, i) -> rs.getTimestamp(1).toInstant(), userId, Timestamp.from(clock.instant().minus(window)));
    }

    /**
     * The last {@code window} of a user's calls: how many counted, how many failed to reach the provider, and the
     * tokens the provider reported. Token totals are over the calls that reported them; {@code callsWithoutUsage}
     * says how many did not, so a total is never read as complete when it is not.
     */
    public Map<String, Object> summary(long userId, Duration window) {
        return jdbc.queryForObject("""
                SELECT count(*) FILTER (WHERE outcome IN ('ok', 'provider_error'))                       AS counted,
                       count(*) FILTER (WHERE outcome = 'unreachable')                                   AS unreachable,
                       coalesce(sum(prompt_tokens), 0)                                                   AS prompt_tokens,
                       coalesce(sum(completion_tokens), 0)                                               AS completion_tokens,
                       count(*) FILTER (WHERE outcome = 'ok' AND (prompt_tokens IS NULL OR completion_tokens IS NULL))
                                                                                                         AS without_usage
                FROM desk.model_call WHERE user_id = ? AND called_at > ?
                """, (rs, i) -> {
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("modelCalls", rs.getLong("counted"));
            out.put("unreachableCalls", rs.getLong("unreachable"));
            out.put("promptTokens", rs.getLong("prompt_tokens"));
            out.put("completionTokens", rs.getLong("completion_tokens"));
            out.put("callsWithoutUsage", rs.getLong("without_usage"));
            return out;
        }, userId, Timestamp.from(clock.instant().minus(window)));
    }

    private static String truncate(String value, int max) {
        return value == null || value.length() <= max ? value : value.substring(0, max);
    }
}
