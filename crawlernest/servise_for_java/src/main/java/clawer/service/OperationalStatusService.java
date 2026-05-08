package clawer.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class OperationalStatusService {

    private final JdbcTemplate jdbcTemplate;

    public OperationalStatusService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Map<String, Object> getOperationalStatus() {
        Map<String, Object> data = new LinkedHashMap<>();

        data.put("last_pipeline_run", buildLastPipelineRun());
        data.put("last_ingestion", buildLastIngestion());
        data.put("unresolved_trend", buildUnresolvedTrend());

        return data;
    }

    // ── Last successful aggregation run ──────────────────────────────────────

    private Map<String, Object> buildLastPipelineRun() {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT aggregation_run_id, ranking_year, status, started_at, finished_at,
                       output_record_count
                FROM analytics.aggregation_runs
                WHERE status = 'finished'
                ORDER BY aggregation_run_id DESC
                LIMIT 1
                """);
        if (rows.isEmpty()) {
            return Map.of(
                    "run_id", (Object) null,
                    "ranking_year", null,
                    "status", "never_run",
                    "finished_at", null,
                    "age_hours", null,
                    "output_count", 0
            );
        }
        Map<String, Object> row = rows.get(0);
        Instant finished = toInstant(row.get("finished_at"));
        long ageHours = finished != null ? ChronoUnit.HOURS.between(finished, Instant.now()) : -1;

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("run_id", row.get("aggregation_run_id"));
        result.put("ranking_year", row.get("ranking_year"));
        result.put("status", row.get("status"));
        result.put("finished_at", finished != null ? finished.toString() : null);
        result.put("age_hours", finished != null ? ageHours : null);
        result.put("output_count", row.get("output_record_count"));
        return result;
    }

    // ── Last ingestion batch ──────────────────────────────────────────────────

    private Map<String, Object> buildLastIngestion() {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT source_code, batch_id, started_at, finished_at,
                       records_in, matched_count, unresolved_count, inserted_count
                FROM analytics.source_ingestion_log
                ORDER BY started_at DESC
                LIMIT 1
                """);
        if (rows.isEmpty()) {
            return Map.of(
                    "source_code", (Object) null,
                    "started_at", null,
                    "records_in", 0,
                    "unresolved_count", 0
            );
        }
        Map<String, Object> row = rows.get(0);
        Instant startedAt = toInstant(row.get("started_at"));
        long ageHours = startedAt != null ? ChronoUnit.HOURS.between(startedAt, Instant.now()) : -1;

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("source_code", row.get("source_code"));
        result.put("batch_id", row.get("batch_id"));
        result.put("started_at", startedAt != null ? startedAt.toString() : null);
        result.put("age_hours", startedAt != null ? ageHours : null);
        result.put("records_in", row.get("records_in"));
        result.put("matched_count", row.get("matched_count"));
        result.put("unresolved_count", row.get("unresolved_count"));
        result.put("inserted_count", row.get("inserted_count"));
        return result;
    }

    // ── Unresolved trend (7-day comparison) ──────────────────────────────────

    private Map<String, Object> buildUnresolvedTrend() {
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM analytics.missing_entity_log", Long.class);

        Long last7d = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM analytics.missing_entity_log "
                + "WHERE created_at >= NOW() - INTERVAL '7 days'",
                Long.class);

        Long prior7d = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM analytics.missing_entity_log "
                + "WHERE created_at >= NOW() - INTERVAL '14 days' "
                + "  AND created_at < NOW() - INTERVAL '7 days'",
                Long.class);

        long t = total != null ? total : 0L;
        long l7 = last7d != null ? last7d : 0L;
        long p7 = prior7d != null ? prior7d : 0L;
        Double trendPct = p7 > 0 ? Math.round((l7 - p7) * 1000.0 / p7) / 10.0 : null;

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", t);
        result.put("last_7d", l7);
        result.put("prior_7d", p7);
        result.put("trend_pct", trendPct);
        result.put("trend_direction",
                trendPct == null ? "stable" :
                trendPct > 5 ? "increasing" :
                trendPct < -5 ? "decreasing" : "stable");
        return result;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static Instant toInstant(Object obj) {
        if (obj == null) return null;
        if (obj instanceof java.sql.Timestamp ts) return ts.toInstant();
        if (obj instanceof java.time.OffsetDateTime odt) return odt.toInstant();
        return null;
    }
}
