package clawer.desk.essay;

import clawer.desk.service.DeskOwnership;
import clawer.desk.support.DeskException;
import clawer.desk.support.DeskInput;
import clawer.service.AnalyticsService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * Essay reviews (desk.essay_review): validate a draft, score it once, store it,
 * read it back.
 *
 * <p>A draft the user has already had scored under the current rubric is not
 * sent to the model again: the stored review comes back with {@code cached: true}.
 * Re-scoring an unchanged draft would only show the model's own variance as if
 * the essay had changed.
 *
 * <p>The model call happens before any write and outside any transaction. If it
 * fails or answers with something unreadable, nothing is stored.
 */
@Service
public class EssayService {

    static final int MAX_DRAFT = 20000;
    static final int MAX_TITLE = 200;
    static final int MAX_PROMPT = 2000;

    private static final Set<String> FIELDS = Set.of("essayTitle", "essayPrompt", "targetEntityId", "revisionOfId", "draftText");

    public static final List<String> CAVEATS = List.of(
            AnalyticsService.ESSAY_SCORE_ESTIMATE_CAVEAT,
            AnalyticsService.ESSAY_OVERALL_METHOD_CAVEAT);

    public record Summary(long id, String essayTitle, BigDecimal overallScore, int wordCount, String rubricVersion,
                          Long revisionOfId, Long targetEntityId, Instant createdAt) {}

    private final JdbcTemplate jdbc;
    private final EssayEvaluator evaluator;
    private final EssayRubric rubric;
    private final DeskOwnership ownership;
    private final ObjectMapper objectMapper;

    public EssayService(JdbcTemplate jdbc, EssayEvaluator evaluator, EssayRubric rubric,
                        DeskOwnership ownership, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.evaluator = evaluator;
        this.rubric = rubric;
        this.ownership = ownership;
        this.objectMapper = objectMapper;
    }

    public Map<String, Object> evaluate(long userId, JsonNode body) {
        DeskInput in = new DeskInput(body, FIELDS);
        String title = in.text("essayTitle", MAX_TITLE, true);
        String essayPrompt = in.text("essayPrompt", MAX_PROMPT, false);
        Long targetEntityId = in.id("targetEntityId", false);
        Long revisionOfId = in.id("revisionOfId", false);
        // The draft is not trimmed: offsets are into exactly the text the user sent.
        JsonNode draftNode = in.node("draftText");
        if (draftNode == null || !draftNode.isTextual() || draftNode.asText().isBlank()) {
            throw DeskException.badRequest("draftText is required.");
        }
        String draft = draftNode.asText();
        if (draft.length() > MAX_DRAFT) {
            throw DeskException.badRequest("draftText must be " + MAX_DRAFT + " characters or fewer.");
        }
        ownership.require("desk.target_entity", targetEntityId, userId, "target");
        if (revisionOfId != null) {
            Boolean owned = jdbc.queryForObject(
                    "SELECT EXISTS (SELECT 1 FROM desk.essay_review WHERE id = ? AND user_id = ?)",
                    Boolean.class, revisionOfId, userId);
            if (!Boolean.TRUE.equals(owned)) {
                throw DeskException.badRequest("No such earlier draft.");
            }
        }

        String sha = sha256(draft);
        Optional<Long> existing = findByDraft(userId, sha);
        if (existing.isPresent()) {
            return detail(userId, existing.get(), true).orElseThrow();
        }

        EssayEvaluator.Evaluation evaluation = evaluator.evaluate(draft, essayPrompt);
        BigDecimal overall = rubric.overall(evaluation.scores());

        List<Long> inserted = jdbc.queryForList("""
                INSERT INTO desk.essay_review
                    (user_id, essay_title, essay_prompt, target_entity_id, revision_of_id, draft_text, word_count,
                     draft_sha256, rubric_version, dimension_scores, overall_score, suggestions, model_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, ?, ?::jsonb, ?)
                ON CONFLICT ON CONSTRAINT essay_review_draft_rubric_key DO NOTHING
                RETURNING id
                """, Long.class,
                userId, title, essayPrompt, targetEntityId, revisionOfId, draft, wordCount(draft), sha,
                rubric.version(), toJson(evaluation.dimensions()), overall, toJson(evaluation.suggestions()),
                evaluation.modelName());
        // Empty only if the same draft was stored by a concurrent request a moment ago.
        long id = inserted.isEmpty() ? findByDraft(userId, sha).orElseThrow() : inserted.get(0);
        Map<String, Object> result = detail(userId, id, inserted.isEmpty()).orElseThrow();
        result.put("droppedQuotes", evaluation.droppedQuotes());
        return result;
    }

    public List<Summary> list(long userId) {
        return jdbc.query("""
                SELECT id, essay_title, overall_score, word_count, rubric_version, revision_of_id, target_entity_id, created_at
                FROM desk.essay_review WHERE user_id = ? ORDER BY created_at DESC, id DESC
                """, (rs, n) -> new Summary(rs.getLong("id"), rs.getString("essay_title"), rs.getBigDecimal("overall_score"),
                        rs.getInt("word_count"), rs.getString("rubric_version"),
                        rs.getObject("revision_of_id", Long.class), rs.getObject("target_entity_id", Long.class),
                        rs.getTimestamp("created_at").toInstant()),
                userId);
    }

    public Optional<Map<String, Object>> detail(long userId, long id, boolean cached) {
        List<Map<String, Object>> rows = jdbc.query("""
                SELECT r.id, r.essay_title, r.essay_prompt, r.target_entity_id, r.revision_of_id, r.draft_text,
                       r.word_count, r.rubric_version, r.dimension_scores::text AS dimension_scores, r.overall_score,
                       r.suggestions::text AS suggestions, r.model_name, r.created_at,
                       p.rubric_version AS prev_rubric, p.dimension_scores::text AS prev_scores, p.overall_score AS prev_overall
                FROM desk.essay_review r
                LEFT JOIN desk.essay_review p ON p.id = r.revision_of_id AND p.user_id = r.user_id
                WHERE r.id = ? AND r.user_id = ?
                """, (rs, n) -> {
            Map<String, Object> out = new LinkedHashMap<>();
            JsonNode scores = parse(rs.getString("dimension_scores"));
            String rubricVersion = rs.getString("rubric_version");
            out.put("id", rs.getLong("id"));
            out.put("essayTitle", rs.getString("essay_title"));
            out.put("essayPrompt", rs.getString("essay_prompt"));
            out.put("targetEntityId", rs.getObject("target_entity_id", Long.class));
            out.put("revisionOfId", rs.getObject("revision_of_id", Long.class));
            out.put("cached", cached);
            out.put("draftText", rs.getString("draft_text"));
            out.put("wordCount", rs.getInt("word_count"));
            out.put("rubricVersion", rubricVersion);
            out.put("overall", Map.of("score", rs.getBigDecimal("overall_score"), "method", "weighted_mean",
                    "weights", rubric.weights()));
            out.put("dimensions", dimensionList(scores));
            out.put("suggestions", parse(rs.getString("suggestions")));
            out.put("comparedToRevision", comparison(rs.getObject("revision_of_id", Long.class), rubricVersion,
                    rs.getString("prev_rubric"), rs.getString("prev_scores"), rs.getBigDecimal("prev_overall"),
                    scores, rs.getBigDecimal("overall_score")));
            out.put("isEstimated", true);
            Timestamp created = rs.getTimestamp("created_at");
            out.put("provenance", Map.of("model", rs.getString("model_name"), "evaluatedAt", created.toInstant()));
            out.put("caveats", CAVEATS);
            return out;
        }, id, userId);
        return rows.stream().findFirst();
    }

    public boolean delete(long userId, long id) {
        return jdbc.update("DELETE FROM desk.essay_review WHERE id = ? AND user_id = ?", id, userId) > 0;
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    private Optional<Long> findByDraft(long userId, String sha) {
        return jdbc.queryForList("""
                SELECT id FROM desk.essay_review WHERE user_id = ? AND draft_sha256 = ? AND rubric_version = ?
                """, Long.class, userId, sha, rubric.version()).stream().findFirst();
    }

    /** Dimensions in rubric order, with the label the UI shows. */
    private List<Map<String, Object>> dimensionList(JsonNode scores) {
        List<Map<String, Object>> list = new ArrayList<>();
        for (EssayRubric.Dimension d : rubric.dimensions()) {
            JsonNode s = scores.path(d.key());
            if (s.isMissingNode()) continue;
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("key", d.key());
            item.put("label", d.label());
            item.put("score", s.path("score").asInt());
            item.put("rationale", s.path("rationale").asText());
            item.put("evidence", s.path("evidence"));
            list.add(item);
        }
        return list;
    }

    /**
     * Score changes against the draft this one revises. Null when there is none,
     * or when the two were scored under different rubrics -- a delta across rubric
     * versions would compare two different scales.
     */
    private Map<String, Object> comparison(Long revisionOfId, String rubricVersion, String prevRubric, String prevScores,
                                           BigDecimal prevOverall, JsonNode scores, BigDecimal overall) {
        if (revisionOfId == null || prevScores == null || !rubricVersion.equals(prevRubric)) {
            return null;
        }
        JsonNode prev = parse(prevScores);
        Map<String, Integer> deltas = new LinkedHashMap<>();
        for (String key : rubric.keys()) {
            if (scores.has(key) && prev.has(key)) {
                deltas.put(key, scores.path(key).path("score").asInt() - prev.path(key).path("score").asInt());
            }
        }
        return Map.of("id", revisionOfId, "overallDelta", overall.subtract(prevOverall), "dimensionDeltas", deltas);
    }

    static int wordCount(String text) {
        String trimmed = text.trim();
        return trimmed.isEmpty() ? 0 : trimmed.split("\\s+").length;
    }

    static String sha256(String text) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private JsonNode parse(String json) {
        try {
            return objectMapper.readTree(json);
        } catch (Exception e) {
            return objectMapper.createObjectNode();
        }
    }
}
