package clawer.user.service;

import clawer.user.dto.SavedRecommendationDetail;
import clawer.user.dto.SavedRecommendationSummary;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.Timestamp;
import java.util.List;
import java.util.Optional;

@Service
public class SavedRecommendationService {

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public SavedRecommendationService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public long save(long userId, String title, JsonNode requestJson, JsonNode resultJson) {
        try {
            String reqStr = objectMapper.writeValueAsString(requestJson);
            String resStr = objectMapper.writeValueAsString(resultJson);
            Long id = jdbcTemplate.queryForObject(
                    """
                    INSERT INTO warehouse.saved_recommendation
                        (user_id, title, request_json, result_json)
                    VALUES (?, ?, ?::jsonb, ?::jsonb)
                    RETURNING id
                    """,
                    Long.class,
                    userId, title, reqStr, resStr);
            return id != null ? id : -1L;
        } catch (Exception e) {
            throw new RuntimeException("Failed to save recommendation", e);
        }
    }

    public List<SavedRecommendationSummary> findSummariesByUserId(long userId) {
        return jdbcTemplate.query("""
                SELECT
                    id,
                    title,
                    created_at,
                    TRIM(CONCAT_WS(', ',
                        NULLIF(request_json->>'country', ''),
                        CASE WHEN request_json->>'ielts' IS NOT NULL
                             THEN 'IELTS ' || (request_json->>'ielts')
                             ELSE NULL END,
                        CASE WHEN request_json->>'targetRank' IS NOT NULL
                             THEN 'Rank #' || (request_json->>'targetRank')
                             ELSE NULL END,
                        NULLIF(request_json->>'riskProfile', '')
                    )) AS request_summary,
                    COALESCE(
                        result_json->'data'->'reach'->0->>'universityName',
                        result_json->'data'->'target'->0->>'universityName'
                    ) AS top_recommendation_name
                FROM warehouse.saved_recommendation
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (rs, rowNum) -> {
                    SavedRecommendationSummary s = new SavedRecommendationSummary();
                    s.setId(rs.getLong("id"));
                    s.setTitle(rs.getString("title"));
                    Timestamp ts = rs.getTimestamp("created_at");
                    s.setCreatedAt(ts != null ? ts.toInstant() : null);
                    s.setRequestSummary(rs.getString("request_summary"));
                    s.setTopRecommendationName(rs.getString("top_recommendation_name"));
                    return s;
                },
                userId);
    }

    public Optional<SavedRecommendationDetail> findDetailByIdAndUserId(long id, long userId) {
        List<SavedRecommendationDetail> results = jdbcTemplate.query("""
                SELECT id, title, created_at, request_json, result_json
                FROM warehouse.saved_recommendation
                WHERE id = ? AND user_id = ?
                """,
                (rs, rowNum) -> {
                    SavedRecommendationDetail d = new SavedRecommendationDetail();
                    d.setId(rs.getLong("id"));
                    d.setTitle(rs.getString("title"));
                    Timestamp ts = rs.getTimestamp("created_at");
                    d.setCreatedAt(ts != null ? ts.toInstant() : null);
                    d.setRequestJson(parseJson(rs.getString("request_json")));
                    d.setResultJson(parseJson(rs.getString("result_json")));
                    return d;
                },
                id, userId);
        return results.isEmpty() ? Optional.empty() : Optional.of(results.get(0));
    }

    public boolean deleteByIdAndUserId(long id, long userId) {
        int rows = jdbcTemplate.update(
                "DELETE FROM warehouse.saved_recommendation WHERE id = ? AND user_id = ?",
                id, userId);
        return rows > 0;
    }

    private Object parseJson(String json) {
        if (json == null) {
            return null;
        }
        try {
            return objectMapper.readTree(json);
        } catch (Exception e) {
            return json;
        }
    }
}
