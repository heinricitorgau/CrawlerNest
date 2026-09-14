package clawer.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Health counts for the held editions only.
 *
 * <p>These used to span every edition loaded, released or not, on the reasoning
 * that an operator auditing a shadow ingest wants to see it. The system-status
 * page renders them, though, so the 2025 shadow load showed up there as
 * per-source 2025 counts and an inflated row total. Shadow editions are audited
 * against the warehouse directly; what this endpoint reports is the release.
 */
@Service
public class HealthService {
    private final JdbcTemplate jdbcTemplate;
    private final DatasetScope datasetScope;

    public HealthService(JdbcTemplate jdbcTemplate, DatasetScope datasetScope) {
        this.jdbcTemplate = jdbcTemplate;
        this.datasetScope = datasetScope;
    }

    public Map<String, Object> getHealth() {
        Map<String, Object> data = new LinkedHashMap<>();

        boolean postgresConnected;
        try {
            jdbcTemplate.queryForObject("SELECT 1", Integer.class);
            postgresConnected = true;
        } catch (Exception ignored) {
            postgresConnected = false;
        }
        data.put("postgres_connected", postgresConnected);

        if (!postgresConnected) {
            data.put("aggregated_rankings_count", 0);
            data.put("subject_rankings_count", 0);
            data.put("latest_ranking_year", null);
            data.put("latest_subject_year", null);
            data.put("sources", List.of());
            return data;
        }

        String held = datasetScope.heldYearsSqlArray();
        Long aggCount = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM analytics.v_aggregated_rankings_latest WHERE ranking_year = ANY(?::int[])",
                Long.class, held);
        data.put("aggregated_rankings_count", aggCount != null ? aggCount : 0L);

        Long subjectCount = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM analytics.v_subject_rankings_latest", Long.class);
        data.put("subject_rankings_count", subjectCount != null ? subjectCount : 0L);

        Integer latestRankingYear = jdbcTemplate.queryForObject(
                "SELECT MAX(ranking_year) FROM analytics.v_aggregated_rankings_latest WHERE ranking_year = ANY(?::int[])",
                Integer.class, held);
        data.put("latest_ranking_year", latestRankingYear);

        Integer latestSubjectYear = jdbcTemplate.queryForObject(
                "SELECT MAX(ranking_year) FROM analytics.v_subject_rankings_latest", Integer.class);
        data.put("latest_subject_year", latestSubjectYear);

        List<Map<String, Object>> sources = jdbcTemplate.queryForList("""
                SELECT rs.source_code, rr.ranking_year, count(*) AS count
                FROM warehouse.ranking_record rr
                JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
                WHERE rr.ranking_year = ANY(?::int[])
                GROUP BY rs.source_code, rr.ranking_year
                ORDER BY rr.ranking_year DESC, rs.source_code
                """, held);
        data.put("sources", sources.stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_code", row.get("source_code"));
            item.put("year", row.get("ranking_year"));
            item.put("count", row.get("count"));
            return item;
        }).toList());

        return data;
    }
}
