package clawer.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class DataQualityService {

    private final JdbcTemplate jdbcTemplate;
    private final DatasetScope datasetScope;

    public DataQualityService(JdbcTemplate jdbcTemplate, DatasetScope datasetScope) {
        this.jdbcTemplate = jdbcTemplate;
        this.datasetScope = datasetScope;
    }

    public Map<String, Object> getDataQuality() {
        Map<String, Object> data = new LinkedHashMap<>();

        data.put("unresolved", buildUnresolved());
        data.put("duplicates", buildDuplicates());
        data.put("drift_warnings", buildDriftWarnings());
        data.put("regression_summary", buildRegressionSummary());
        data.put("low_confidence_matches", buildLowConfidenceMatches());
        data.put("evaluation_timestamp", Instant.now().toString());

        return data;
    }

    // ── Unresolved universities ───────────────────────────────────────────────

    private Map<String, Object> buildUnresolved() {
        Map<String, Object> section = new LinkedHashMap<>();

        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM analytics.missing_entity_log", Long.class);
        section.put("total", total != null ? total : 0L);

        List<Map<String, Object>> bySource = jdbcTemplate.queryForList("""
                SELECT source_code, COUNT(*) AS count
                FROM analytics.missing_entity_log
                GROUP BY source_code
                ORDER BY count DESC
                """);
        section.put("by_source", bySource.stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_code", row.get("source_code"));
            item.put("count", row.get("count"));
            return item;
        }).toList());

        List<Map<String, Object>> examples = jdbcTemplate.queryForList("""
                SELECT source_code, raw_name, country_hint, ranking_year
                FROM analytics.missing_entity_log
                ORDER BY created_at DESC
                LIMIT 5
                """);
        section.put("top_examples", examples.stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_code", row.get("source_code"));
            item.put("raw_name", row.get("raw_name"));
            item.put("country_hint", row.get("country_hint"));
            item.put("ranking_year", row.get("ranking_year"));
            return item;
        }).toList());

        return section;
    }

    // ── Duplicate resolution ──────────────────────────────────────────────────

    private Map<String, Object> buildDuplicates() {
        Map<String, Object> section = new LinkedHashMap<>();

        Long totalSaves = jdbcTemplate.queryForObject(
                "SELECT COALESCE(SUM(duplicate_resolution_saves), 0) FROM analytics.merge_diagnostics",
                Long.class);
        section.put("total_duplicate_saves", totalSaves != null ? totalSaves : 0L);

        List<Map<String, Object>> bySource = jdbcTemplate.queryForList("""
                SELECT source_code, SUM(duplicate_resolution_saves) AS saves
                FROM analytics.merge_diagnostics
                GROUP BY source_code
                ORDER BY saves DESC
                """);
        section.put("by_source", bySource.stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_code", row.get("source_code"));
            item.put("duplicate_resolution_saves", row.get("saves"));
            return item;
        }).toList());

        return section;
    }

    // ── Source drift warnings ─────────────────────────────────────────────────

    private List<Map<String, Object>> buildDriftWarnings() {
        List<Map<String, Object>> warnings = new ArrayList<>();

        // Compare the last two ingestion batches per source for count drops
        List<Map<String, Object>> logRows = jdbcTemplate.queryForList("""
                SELECT source_code, records_in, unresolved_count, started_at
                FROM analytics.source_ingestion_log
                ORDER BY source_code, started_at DESC
                """);

        Map<String, List<Map<String, Object>>> bySource = new LinkedHashMap<>();
        for (Map<String, Object> row : logRows) {
            String src = (String) row.get("source_code");
            bySource.computeIfAbsent(src, k -> new ArrayList<>()).add(row);
        }

        for (Map.Entry<String, List<Map<String, Object>>> entry : bySource.entrySet()) {
            List<Map<String, Object>> batches = entry.getValue();
            if (batches.size() < 2) continue;

            Map<String, Object> newer = batches.get(0);
            Map<String, Object> older = batches.get(1);

            long newCount = toLong(newer.get("records_in"));
            long oldCount = toLong(older.get("records_in"));

            if (oldCount > 0) {
                double dropRatio = (double)(oldCount - newCount) / oldCount;
                if (dropRatio > 0.20) {
                    Map<String, Object> w = new LinkedHashMap<>();
                    w.put("source_code", entry.getKey());
                    w.put("warning_type", "count_drop");
                    w.put("message", String.format(
                            "records_in dropped from %d to %d (%.0f%% drop)",
                            oldCount, newCount, dropRatio * 100));
                    w.put("previous_count", oldCount);
                    w.put("current_count", newCount);
                    w.put("drop_pct", Math.round(dropRatio * 1000) / 10.0);
                    warnings.add(w);
                }

                long newUnresolved = toLong(newer.get("unresolved_count"));
                long oldUnresolved = toLong(older.get("unresolved_count"));
                if (oldUnresolved > 0 && newUnresolved > oldUnresolved * 1.5) {
                    Map<String, Object> w = new LinkedHashMap<>();
                    w.put("source_code", entry.getKey());
                    w.put("warning_type", "unresolved_spike");
                    w.put("message", String.format(
                            "unresolved_count increased from %d to %d",
                            oldUnresolved, newUnresolved));
                    w.put("previous_unresolved", oldUnresolved);
                    w.put("current_unresolved", newUnresolved);
                    warnings.add(w);
                }
            }
        }

        // Check for sources with zero records in the latest aggregated view
        List<Map<String, Object>> zeroSources = jdbcTemplate.queryForList("""
                SELECT rs.source_code
                FROM warehouse.ranking_source rs
                WHERE rs.is_active = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM warehouse.ranking_record rr
                      WHERE rr.ranking_source_id = rs.ranking_source_id
                  )
                """);
        for (Map<String, Object> row : zeroSources) {
            Map<String, Object> w = new LinkedHashMap<>();
            w.put("source_code", row.get("source_code"));
            w.put("warning_type", "source_empty");
            w.put("message", "Active source has no records in warehouse.ranking_record");
            warnings.add(w);
        }

        return warnings;
    }

    // ── Regression summary (DB-derived) ──────────────────────────────────────

    private Map<String, Object> buildRegressionSummary() {
        Map<String, Object> section = new LinkedHashMap<>();

        // The default edition: a count and score range summed over editions would
        // shift the moment an unreleased edition is loaded, and read as a regression.
        int edition = datasetScope.defaultRankingYear();
        Long aggCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM analytics.v_aggregated_rankings_latest WHERE ranking_year = ?",
                Long.class, edition);
        section.put("aggregated_count", aggCount != null ? aggCount : 0L);

        List<Map<String, Object>> scoreStats = jdbcTemplate.queryForList("""
                SELECT
                    MIN(composite_score) AS score_min,
                    MAX(composite_score) AS score_max,
                    ROUND(AVG(composite_score)::NUMERIC, 4) AS score_avg
                FROM analytics.v_aggregated_rankings_latest
                WHERE composite_score IS NOT NULL
                  AND ranking_year = ?
                """, edition);
        if (!scoreStats.isEmpty()) {
            Map<String, Object> stats = scoreStats.get(0);
            section.put("score_min", stats.get("score_min"));
            section.put("score_max", stats.get("score_max"));
            section.put("score_avg", stats.get("score_avg"));
        } else {
            section.put("score_min", null);
            section.put("score_max", null);
            section.put("score_avg", null);
        }

        Long lowCoverage = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM analytics.v_aggregated_rankings_latest WHERE coverage_ratio < 0.5 AND ranking_year = ?",
                Long.class, edition);
        section.put("low_coverage_count", lowCoverage != null ? lowCoverage : 0L);

        return section;
    }

    // ── Low-confidence canonical matches ─────────────────────────────────────

    private Map<String, Object> buildLowConfidenceMatches() {
        Map<String, Object> section = new LinkedHashMap<>();
        double threshold = 0.80;
        section.put("threshold", threshold);

        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM warehouse.source_mapping WHERE confidence_score < ? AND is_active = TRUE",
                Long.class, threshold);
        section.put("count", count != null ? count : 0L);

        List<Map<String, Object>> examples = jdbcTemplate.queryForList("""
                SELECT sm.source_name, sm.confidence_score, sm.match_method,
                       cu.canonical_slug, cu.display_name
                FROM warehouse.source_mapping sm
                JOIN warehouse.canonical_university cu
                  ON cu.canonical_university_id = sm.canonical_university_id
                WHERE sm.confidence_score < 0.80 AND sm.is_active = TRUE
                ORDER BY sm.confidence_score ASC
                LIMIT 5
                """);
        section.put("examples", examples.stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_name", row.get("source_name"));
            item.put("confidence_score", row.get("confidence_score"));
            item.put("match_method", row.get("match_method"));
            item.put("canonical_slug", row.get("canonical_slug"));
            item.put("display_name", row.get("display_name"));
            return item;
        }).toList());

        return section;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static long toLong(Object obj) {
        if (obj == null) return 0L;
        if (obj instanceof Long l) return l;
        if (obj instanceof Integer i) return i.longValue();
        if (obj instanceof Number n) return n.longValue();
        return 0L;
    }
}
