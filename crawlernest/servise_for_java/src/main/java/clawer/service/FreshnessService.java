package clawer.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class FreshnessService {
    private static final long STALE_THRESHOLD_HOURS = 30L * 24;

    private final JdbcTemplate jdbcTemplate;
    private final DatasetScope datasetScope;

    public FreshnessService(JdbcTemplate jdbcTemplate, DatasetScope datasetScope) {
        this.jdbcTemplate = jdbcTemplate;
        this.datasetScope = datasetScope;
    }

    /**
     * Freshness of the held editions. Reading every edition made a shadow load the
     * "latest" year and the latest aggregation run, on a page users see.
     */
    public Map<String, Object> getFreshness() {
        Map<String, Object> data = new LinkedHashMap<>();
        String held = datasetScope.heldYearsSqlArray();

        List<String> allSources = jdbcTemplate.queryForList(
                "SELECT source_code FROM warehouse.ranking_source WHERE is_active = TRUE ORDER BY source_code",
                String.class);

        List<Map<String, Object>> sourceRows = jdbcTemplate.queryForList("""
                SELECT rs.source_code,
                       MAX(rr.ingested_at) AS latest_ingested_at,
                       MAX(rr.updated_at)  AS latest_updated_at,
                       COUNT(*)            AS record_count,
                       MAX(rr.ranking_year) AS latest_year
                FROM warehouse.ranking_record rr
                JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
                WHERE rr.ranking_year = ANY(?::int[])
                GROUP BY rs.source_code
                ORDER BY rs.source_code
                """, held);

        Map<String, Map<String, Object>> sourceDataMap = new LinkedHashMap<>();
        for (Map<String, Object> row : sourceRows) {
            sourceDataMap.put((String) row.get("source_code"), row);
        }

        Instant maxGlobalIngested = null;
        List<Map<String, Object>> globalRankings = new ArrayList<>();
        List<String> missingSources = new ArrayList<>();

        for (String sourceCode : allSources) {
            Map<String, Object> row = sourceDataMap.get(sourceCode);
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("source_code", sourceCode);

            if (row == null) {
                entry.put("latest_ingested_at", null);
                entry.put("latest_updated_at", null);
                entry.put("latest_year", null);
                entry.put("record_count", 0);
                entry.put("age_hours", null);
                entry.put("stale", true);
                entry.put("missing", true);
                missingSources.add(sourceCode);
            } else {
                Instant ingestedAt = toInstant(row.get("latest_ingested_at"));
                long ageHours = ingestedAt != null
                        ? ChronoUnit.HOURS.between(ingestedAt, Instant.now()) : -1;
                boolean stale = ingestedAt == null || ageHours > STALE_THRESHOLD_HOURS;

                entry.put("latest_ingested_at", ingestedAt != null ? ingestedAt.toString() : null);
                entry.put("latest_updated_at", toInstantStr(row.get("latest_updated_at")));
                entry.put("latest_year", row.get("latest_year"));
                entry.put("record_count", row.get("record_count"));
                entry.put("age_hours", ingestedAt != null ? ageHours : null);
                entry.put("stale", stale);
                entry.put("missing", false);

                if (ingestedAt != null
                        && (maxGlobalIngested == null || ingestedAt.isAfter(maxGlobalIngested))) {
                    maxGlobalIngested = ingestedAt;
                }
            }
            globalRankings.add(entry);
        }

        data.put("global_rankings", globalRankings);
        data.put("missing_sources", missingSources);

        List<Map<String, Object>> subjectRows = jdbcTemplate.queryForList("""
                SELECT subj.subject_key, subj.display_name,
                       MAX(srr.ingested_at)  AS latest_ingested_at,
                       MAX(srr.updated_at)   AS latest_updated_at,
                       COUNT(srr.subject_ranking_record_id) AS record_count,
                       MAX(srr.ranking_year) AS latest_year
                FROM warehouse.ranking_subject subj
                LEFT JOIN warehouse.subject_ranking_record srr ON srr.subject_id = subj.subject_id
                WHERE subj.is_active = TRUE
                GROUP BY subj.subject_key, subj.display_name
                ORDER BY subj.display_name
                """);

        List<Map<String, Object>> subjectRankings = new ArrayList<>();
        for (Map<String, Object> row : subjectRows) {
            Map<String, Object> entry = new LinkedHashMap<>();
            Instant ingestedAt = toInstant(row.get("latest_ingested_at"));
            long ageHours = ingestedAt != null
                    ? ChronoUnit.HOURS.between(ingestedAt, Instant.now()) : -1;
            boolean missing = ingestedAt == null;
            boolean stale = missing || ageHours > STALE_THRESHOLD_HOURS;

            entry.put("subject_key", row.get("subject_key"));
            entry.put("subject_name", row.get("display_name"));
            entry.put("latest_ingested_at", ingestedAt != null ? ingestedAt.toString() : null);
            entry.put("latest_updated_at", toInstantStr(row.get("latest_updated_at")));
            entry.put("latest_year", row.get("latest_year"));
            entry.put("record_count", row.get("record_count"));
            entry.put("age_hours", ingestedAt != null ? ageHours : null);
            entry.put("stale", stale);
            entry.put("missing", missing);

            subjectRankings.add(entry);
        }
        data.put("subject_rankings", subjectRankings);

        List<Map<String, Object>> aggRuns = jdbcTemplate.queryForList("""
                SELECT aggregation_run_id, ranking_year, status, started_at, finished_at,
                       output_record_count
                FROM analytics.aggregation_runs
                WHERE ranking_year = ANY(?::int[])
                ORDER BY aggregation_run_id DESC
                LIMIT 1
                """, held);

        Map<String, Object> aggregation = new LinkedHashMap<>();
        if (!aggRuns.isEmpty()) {
            Map<String, Object> run = aggRuns.get(0);
            Instant finishedAt = toInstant(run.get("finished_at"));
            if (finishedAt == null) finishedAt = toInstant(run.get("started_at"));
            long aggAgeHours = finishedAt != null
                    ? ChronoUnit.HOURS.between(finishedAt, Instant.now()) : -1;
            boolean aggStale = finishedAt == null || aggAgeHours > STALE_THRESHOLD_HOURS;
            boolean behindIngestion = finishedAt != null && maxGlobalIngested != null
                    && finishedAt.isBefore(maxGlobalIngested);

            aggregation.put("latest_run_id", run.get("aggregation_run_id"));
            aggregation.put("ranking_year", run.get("ranking_year"));
            aggregation.put("status", run.get("status"));
            aggregation.put("latest_at", finishedAt != null ? finishedAt.toString() : null);
            aggregation.put("age_hours", finishedAt != null ? aggAgeHours : null);
            aggregation.put("stale", aggStale);
            aggregation.put("behind_ingestion", behindIngestion);
            aggregation.put("output_count", run.get("output_record_count"));
        } else {
            aggregation.put("latest_run_id", null);
            aggregation.put("ranking_year", null);
            aggregation.put("status", null);
            aggregation.put("latest_at", null);
            aggregation.put("age_hours", null);
            aggregation.put("stale", true);
            aggregation.put("behind_ingestion", false);
            aggregation.put("output_count", 0);
        }
        data.put("aggregation", aggregation);

        boolean anySourceStale = globalRankings.stream()
                .anyMatch(e -> Boolean.TRUE.equals(e.get("stale")));
        boolean aggStaleOrBehind = Boolean.TRUE.equals(aggregation.get("stale"))
                || Boolean.TRUE.equals(aggregation.get("behind_ingestion"));
        data.put("overall_stale", anySourceStale || aggStaleOrBehind);

        return data;
    }

    private static Instant toInstant(Object obj) {
        if (obj == null) return null;
        if (obj instanceof java.sql.Timestamp ts) return ts.toInstant();
        if (obj instanceof java.time.OffsetDateTime odt) return odt.toInstant();
        return null;
    }

    private static String toInstantStr(Object obj) {
        Instant inst = toInstant(obj);
        return inst != null ? inst.toString() : null;
    }
}
