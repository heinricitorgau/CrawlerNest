package clawer.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class HealthService {
    private final JdbcTemplate jdbcTemplate;

    public HealthService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
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

        Long aggCount = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM analytics.v_aggregated_rankings_latest", Long.class);
        data.put("aggregated_rankings_count", aggCount != null ? aggCount : 0L);

        Long subjectCount = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM analytics.v_subject_rankings_latest", Long.class);
        data.put("subject_rankings_count", subjectCount != null ? subjectCount : 0L);

        Integer latestRankingYear = jdbcTemplate.queryForObject(
                "SELECT MAX(ranking_year) FROM analytics.v_aggregated_rankings_latest", Integer.class);
        data.put("latest_ranking_year", latestRankingYear);

        Integer latestSubjectYear = jdbcTemplate.queryForObject(
                "SELECT MAX(ranking_year) FROM analytics.v_subject_rankings_latest", Integer.class);
        data.put("latest_subject_year", latestSubjectYear);

        List<Map<String, Object>> sources = jdbcTemplate.queryForList("""
                SELECT rs.source_code, rr.ranking_year, count(*) AS count
                FROM warehouse.ranking_record rr
                JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
                GROUP BY rs.source_code, rr.ranking_year
                ORDER BY rr.ranking_year DESC, rs.source_code
                """);
        data.put("sources", sources.stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_code", row.get("source_code"));
            item.put("year", row.get("ranking_year"));
            item.put("count", row.get("count"));
            return item;
        }).toList());

        try {
            Long userCount = jdbcTemplate.queryForObject(
                    "SELECT count(*) FROM warehouse.app_user", Long.class);
            data.put("app_user_count", userCount != null ? userCount : 0L);
        } catch (Exception ignored) {
            data.put("app_user_count", 0L);
        }

        return data;
    }
}
