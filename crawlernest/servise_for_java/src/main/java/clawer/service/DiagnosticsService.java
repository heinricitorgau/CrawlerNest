package clawer.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Ranking diagnostics for the held editions. Like {@link HealthService}, these
 * reach a page (system status), so an ingested but unreleased edition stays out.
 * Ingestion logs are the exception: a batch is an event, not an edition's data.
 */
@Service
public class DiagnosticsService {
    private final JdbcTemplate jdbcTemplate;
    private final DatasetScope datasetScope;

    public DiagnosticsService(JdbcTemplate jdbcTemplate, DatasetScope datasetScope) {
        this.jdbcTemplate = jdbcTemplate;
        this.datasetScope = datasetScope;
    }

    public Map<String, Object> getRankingsDiagnostics() {
        Map<String, Object> data = new LinkedHashMap<>();
        String held = datasetScope.heldYearsSqlArray();

        List<Map<String, Object>> sourceCounts = jdbcTemplate.queryForList("""
                SELECT rs.source_code, rr.ranking_year, count(*) AS count
                FROM warehouse.ranking_record rr
                JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
                WHERE rr.ranking_year = ANY(?::int[])
                GROUP BY rs.source_code, rr.ranking_year
                ORDER BY rr.ranking_year DESC, rs.source_code
                """, held);
        data.put("source_counts", sourceCounts.stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_code", row.get("source_code"));
            item.put("year", row.get("ranking_year"));
            item.put("count", row.get("count"));
            return item;
        }).toList());

        Long unresolvedCount = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM analytics.missing_entity_log WHERE ranking_year = ANY(?::int[])", Long.class, held);
        data.put("unresolved_university_count", unresolvedCount != null ? unresolvedCount : 0L);

        Long duplicateCount = jdbcTemplate.queryForObject(
                "SELECT COALESCE(SUM(duplicate_resolution_saves), 0) FROM analytics.merge_diagnostics", Long.class);
        data.put("duplicate_resolution_count", duplicateCount != null ? duplicateCount : 0L);

        Long aggCount = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM analytics.v_aggregated_rankings_latest WHERE ranking_year = ANY(?::int[])",
                Long.class, held);
        data.put("aggregated_latest_count", aggCount != null ? aggCount : 0L);

        List<Map<String, Object>> ingestionLog = jdbcTemplate.queryForList("""
                SELECT source_code, batch_id, started_at, finished_at,
                       records_in, matched_count, unresolved_count, inserted_count, updated_count
                FROM analytics.source_ingestion_log
                ORDER BY started_at DESC
                LIMIT 5
                """);
        data.put("ingestion_log", ingestionLog.stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_code", row.get("source_code"));
            item.put("batch_id", row.get("batch_id"));
            item.put("started_at", row.get("started_at") != null ? row.get("started_at").toString() : null);
            item.put("finished_at", row.get("finished_at") != null ? row.get("finished_at").toString() : null);
            item.put("records_in", row.get("records_in"));
            item.put("matched_count", row.get("matched_count"));
            item.put("unresolved_count", row.get("unresolved_count"));
            item.put("inserted_count", row.get("inserted_count"));
            item.put("updated_count", row.get("updated_count"));
            return item;
        }).toList());

        List<Map<String, Object>> aggRuns = jdbcTemplate.queryForList("""
                SELECT aggregation_run_id, ranking_year, status, started_at, finished_at,
                       input_record_count, output_record_count
                FROM analytics.aggregation_runs
                WHERE ranking_year = ANY(?::int[])
                ORDER BY aggregation_run_id DESC
                LIMIT 1
                """, held);
        if (!aggRuns.isEmpty()) {
            Map<String, Object> run = aggRuns.get(0);
            data.put("latest_aggregation_run_id", run.get("aggregation_run_id"));
            data.put("latest_aggregation_year", run.get("ranking_year"));
            data.put("latest_aggregation_status", run.get("status"));
            data.put("latest_aggregation_timestamp",
                    run.get("finished_at") != null ? run.get("finished_at").toString()
                    : run.get("started_at") != null ? run.get("started_at").toString() : null);
            data.put("latest_aggregation_output_count", run.get("output_record_count"));
        } else {
            data.put("latest_aggregation_run_id", null);
            data.put("latest_aggregation_year", null);
            data.put("latest_aggregation_status", null);
            data.put("latest_aggregation_timestamp", null);
            data.put("latest_aggregation_output_count", 0);
        }

        return data;
    }

    public Map<String, Object> getSubjectsDiagnostics() {
        Map<String, Object> data = new LinkedHashMap<>();

        List<Map<String, Object>> bySubject = jdbcTemplate.queryForList("""
                SELECT rs.subject_key, rs.display_name,
                       COUNT(srr.subject_ranking_record_id) AS row_count,
                       COUNT(DISTINCT srr.canonical_university_id) AS university_count,
                       MAX(srr.ranking_year) AS latest_year
                FROM warehouse.ranking_subject rs
                LEFT JOIN warehouse.subject_ranking_record srr ON srr.subject_id = rs.subject_id
                WHERE rs.is_active = TRUE
                GROUP BY rs.subject_key, rs.display_name
                ORDER BY rs.display_name
                """);
        data.put("by_subject", bySubject.stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("subject_key", row.get("subject_key"));
            item.put("subject_name", row.get("display_name"));
            item.put("row_count", row.get("row_count"));
            item.put("university_count", row.get("university_count"));
            item.put("latest_year", row.get("latest_year"));
            return item;
        }).toList());

        List<Map<String, Object>> countryCoverage = jdbcTemplate.queryForList("""
                SELECT rs.subject_key, c.country_name, COUNT(*) AS count
                FROM warehouse.subject_ranking_record srr
                JOIN warehouse.ranking_subject rs ON rs.subject_id = srr.subject_id
                JOIN warehouse.canonical_university cu
                  ON cu.canonical_university_id = srr.canonical_university_id
                JOIN warehouse.countries c ON c.country_id = cu.country_id
                GROUP BY rs.subject_key, c.country_name
                ORDER BY count DESC
                LIMIT 20
                """);
        data.put("country_coverage", countryCoverage.stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("subject_key", row.get("subject_key"));
            item.put("country_name", row.get("country_name"));
            item.put("count", row.get("count"));
            return item;
        }).toList());

        List<Map<String, Object>> missingCountries = jdbcTemplate.queryForList("""
                SELECT c.country_name, COUNT(DISTINCT ar.canonical_university_id) AS global_count
                FROM analytics.v_aggregated_rankings_latest ar
                JOIN warehouse.canonical_university cu
                  ON cu.canonical_university_id = ar.canonical_university_id
                JOIN warehouse.countries c ON c.country_id = cu.country_id
                WHERE ar.ranking_year = ANY(?::int[])
                  AND NOT EXISTS (
                    SELECT 1 FROM warehouse.subject_ranking_record srr
                    WHERE srr.canonical_university_id = ar.canonical_university_id
                )
                GROUP BY c.country_name
                ORDER BY global_count DESC
                LIMIT 10
                """, datasetScope.heldYearsSqlArray());
        data.put("top_missing_countries", missingCountries.stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("country_name", row.get("country_name"));
            item.put("global_ranking_count", row.get("global_count"));
            return item;
        }).toList());

        return data;
    }
}
