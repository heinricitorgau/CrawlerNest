package clawer.desk.story;

import clawer.desk.model.DeskModelClient;
import clawer.desk.model.ModelJson;
import clawer.desk.model.ModelJson.UnreadableReplyException;
import clawer.desk.support.DeskException;
import clawer.desk.support.DeskInput;
import clawer.service.AnalyticsService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;

/**
 * Narrative themes (desk.user_theme) and resonance (desk.entity_resonance).
 *
 * <p>Both are model output, handled the way essay scores are:
 * <ul>
 *   <li>Themes are drawn from the user's own essay drafts. Every evidence quote
 *       is checked to occur in the draft it names; a theme with no quote left is
 *       dropped, which the table's CHECK would refuse anyway.</li>
 *   <li>A new theme is only a suggestion. The user accepts or dismisses it, and
 *       regenerating replaces the open suggestions, never an accepted theme.</li>
 *   <li>Resonance is judged only for accepted themes. Where the model's view of a
 *       school came from is decided here, not taken from the model: a school
 *       with no notes from the user is always "model_general_knowledge".</li>
 *   <li>Wikipedia text is never an input (CLAUDE.md, "Wikipedia introductions").</li>
 * </ul>
 * The model call happens before any write; a failure or an unusable reply stores nothing.
 */
@Service
public class NarrativeService {

    static final String THEMES_PROMPT_VERSION = "narrative-themes-2026.1";
    static final String RESONANCE_PROMPT_VERSION = "resonance-2026.1";
    static final int MAX_DRAFTS = 6;
    static final int MAX_MATERIAL_CHARS = 40_000;
    static final int MAX_THEMES_FOR_RESONANCE = 3;
    static final int MAX_TARGETS_FOR_RESONANCE = 12;

    private final JdbcTemplate jdbc;
    private final DeskModelClient model;
    private final ObjectMapper objectMapper;
    private final TransactionTemplate tx;
    private final String themesPrompt;
    private final String resonancePrompt;

    public NarrativeService(JdbcTemplate jdbc, DeskModelClient model, ObjectMapper objectMapper, TransactionTemplate tx) {
        this.jdbc = jdbc;
        this.model = model;
        this.objectMapper = objectMapper;
        this.tx = tx;
        this.themesPrompt = readResource("prompts/narrative_themes_system.txt");
        this.resonancePrompt = readResource("prompts/resonance_system.txt");
    }

    // ─── Read ─────────────────────────────────────────────────────────────────

    /** Themes, resonance and caveats together: what every write returns, so the page shows one state. */
    public Map<String, Object> narrative(long userId, boolean includeDismissed) {
        List<Map<String, Object>> resonance = resonanceRows(userId);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("themes", themeRows(userId, includeDismissed));
        out.put("resonance", resonance);
        out.put("caveats", caveats(resonance));
        return out;
    }

    /** GET /story/themes: the themes alone, with the caveat that applies to them. */
    public Map<String, Object> themes(long userId, boolean includeDismissed) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("themes", themeRows(userId, includeDismissed));
        out.put("caveats", List.of(AnalyticsService.NARRATIVE_ESTIMATE_CAVEAT));
        return out;
    }

    /** GET /story/resonance: accepted themes' 1-5 levels against the user's schools, with their caveats. */
    public Map<String, Object> resonance(long userId) {
        List<Map<String, Object>> resonance = resonanceRows(userId);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("resonance", resonance);
        out.put("scale", Map.of("min", 1, "max", 5, "labels", Map.of("5-4", "Strong", "3", "Moderate", "2-1", "Emerging")));
        out.put("caveats", caveats(resonance));
        return out;
    }

    /** The general-knowledge caveat only when a row's school side actually came from it. */
    private static List<String> caveats(List<Map<String, Object>> resonance) {
        List<String> caveats = new ArrayList<>(List.of(AnalyticsService.NARRATIVE_ESTIMATE_CAVEAT));
        if (resonance.stream().anyMatch(r -> "model_general_knowledge".equals(r.get("institutionBasis")))) {
            caveats.add(AnalyticsService.RESONANCE_GENERAL_KNOWLEDGE_CAVEAT);
        }
        return caveats;
    }

    private List<Map<String, Object>> themeRows(long userId, boolean includeDismissed) {
        return jdbc.query("""
                SELECT id, title, summary, traits, evidence::text AS evidence, status, model_name, prompt_version, generated_at, decided_at
                FROM desk.user_theme
                WHERE user_id = ? AND (status <> 'dismissed' OR ?)
                ORDER BY status = 'accepted' DESC, generated_at DESC, id DESC
                """, (rs, n) -> {
            Map<String, Object> t = new LinkedHashMap<>();
            t.put("id", rs.getLong("id"));
            t.put("title", rs.getString("title"));
            t.put("summary", rs.getString("summary"));
            t.put("traits", List.of((String[]) rs.getArray("traits").getArray()));
            t.put("status", rs.getString("status"));
            t.put("evidence", parse(rs.getString("evidence")));
            t.put("isEstimated", true);
            t.put("provenance", Map.of("model", rs.getString("model_name"), "promptVersion", rs.getString("prompt_version"),
                    "generatedAt", rs.getTimestamp("generated_at").toInstant()));
            return t;
        }, userId, includeDismissed);
    }

    private List<Map<String, Object>> resonanceRows(long userId) {
        return jdbc.query("""
                SELECT r.theme_id, r.target_entity_id, r.level, r.rationale, r.institution_basis, r.model_name,
                       r.prompt_version, r.generated_at, coalesce(cu.display_name, t.custom_name) AS institution
                FROM desk.entity_resonance r
                JOIN desk.user_theme th ON th.id = r.theme_id AND th.user_id = r.user_id AND th.status = 'accepted'
                JOIN desk.target_entity t ON t.id = r.target_entity_id AND t.user_id = r.user_id
                LEFT JOIN warehouse.canonical_university cu ON cu.canonical_university_id = t.canonical_university_id
                WHERE r.user_id = ?
                ORDER BY r.theme_id, r.level DESC, institution
                """, (rs, n) -> {
            Map<String, Object> r = new LinkedHashMap<>();
            int level = rs.getInt("level");
            r.put("themeId", rs.getLong("theme_id"));
            r.put("targetEntityId", rs.getLong("target_entity_id"));
            r.put("institution", rs.getString("institution"));
            r.put("level", level);
            r.put("levelLabel", levelLabel(level));
            r.put("rationale", rs.getString("rationale"));
            r.put("institutionBasis", rs.getString("institution_basis"));
            r.put("isEstimated", true);
            r.put("provenance", Map.of("model", rs.getString("model_name"), "promptVersion", rs.getString("prompt_version"),
                    "generatedAt", rs.getTimestamp("generated_at").toInstant()));
            return r;
        }, userId);
    }

    /** The ordinal's words, the same cut as the UI's ResonanceBar. */
    static String levelLabel(int level) {
        return level >= 4 ? "Strong" : level == 3 ? "Moderate" : "Emerging";
    }

    // ─── Themes ───────────────────────────────────────────────────────────────

    private record Draft(long id, String title, String text) {}

    /** A theme ready to store: evidence already checked against its sources. */
    public record Theme(String title, String summary, List<String> traits, ArrayNode evidence) {}

    /** Draws one or two themes from the user's drafts and stores them as suggestions, replacing open ones. */
    public Map<String, Object> generateThemes(long userId) {
        // The latest draft of each essay, newest first: revisions of one essay would
        // otherwise fill the budget with the same sentences.
        List<Draft> drafts = jdbc.query("""
                SELECT id, essay_title, draft_text FROM (
                    SELECT DISTINCT ON (essay_title) id, essay_title, draft_text, created_at
                    FROM desk.essay_review WHERE user_id = ?
                    ORDER BY essay_title, created_at DESC, id DESC
                ) latest ORDER BY created_at DESC, id DESC LIMIT ?
                """, (rs, n) -> new Draft(rs.getLong("id"), rs.getString("essay_title"), rs.getString("draft_text")),
                userId, MAX_DRAFTS);
        if (drafts.isEmpty()) {
            throw DeskException.badRequest("Have at least one essay draft reviewed first: themes are drawn from your own writing.");
        }
        StringBuilder material = new StringBuilder();
        Map<Long, String> sent = new LinkedHashMap<>();
        for (Draft d : drafts) {
            if (!sent.isEmpty() && material.length() + d.text().length() > MAX_MATERIAL_CHARS) break;
            material.append("<draft id=\"").append(d.id()).append("\" title=\"").append(d.title().replace("\"", "'"))
                    .append("\">\n").append(d.text()).append("\n</draft>\n\n");
            sent.put(d.id(), d.text());
        }

        Reply<List<Theme>> reply = completeJson(themesPrompt, material.toString(), root -> parseThemes(root, sent));
        if (reply.value().isEmpty()) {
            throw new UnreadableReplyException(
                    "No theme could be tied to quotes from your drafts, so nothing was stored. Try again after another draft.");
        }

        tx.executeWithoutResult(status -> storeSuggestedThemes(userId, reply.value(), reply.modelName(), THEMES_PROMPT_VERSION));
        return narrative(userId, false);
    }

    /**
     * Replaces the user's open suggestions with these themes; accepted themes are
     * untouched. Run inside the caller's transaction. Also used by Tassel's
     * generate_narrative_themes, whose evidence the tool executor has checked.
     *
     * @return the new themes' ids
     */
    public List<Long> storeSuggestedThemes(long userId, List<Theme> themes, String modelName, String promptVersion) {
        jdbc.update("DELETE FROM desk.user_theme WHERE user_id = ? AND status = 'suggested'", userId);
        List<Long> ids = new ArrayList<>();
        for (Theme t : themes) {
            ids.add(jdbc.query(con -> {
                var ps = con.prepareStatement("""
                        INSERT INTO desk.user_theme (user_id, title, summary, traits, evidence, model_name, prompt_version)
                        VALUES (?, ?, ?, ?, ?::jsonb, ?, ?) RETURNING id
                        """);
                ps.setLong(1, userId);
                ps.setString(2, t.title());
                ps.setString(3, t.summary());
                ps.setArray(4, con.createArrayOf("text", t.traits().toArray()));
                ps.setString(5, t.evidence().toString());
                ps.setString(6, modelName);
                ps.setString(7, promptVersion);
                return ps;
            }, rs -> {
                rs.next();
                return rs.getLong(1);
            }));
        }
        return ids;
    }

    private List<Theme> parseThemes(JsonNode root, Map<Long, String> drafts) {
        JsonNode themes = root.path("themes");
        if (!themes.isArray()) {
            throw new UnreadableReplyException("\"themes\" was missing or not a list.");
        }
        List<Theme> kept = new ArrayList<>();
        for (JsonNode t : themes) {
            if (kept.size() == 2) break;
            String title = t.path("title").asText("").trim();
            String summary = t.path("summary").asText("").trim();
            if (title.isEmpty() || summary.isEmpty()) continue;
            List<String> traits = new ArrayList<>();
            for (JsonNode trait : t.path("traits")) {
                String text = trait.asText("").trim();
                if (!text.isEmpty() && traits.size() < 5) traits.add(truncate(text, 40));
            }
            ArrayNode evidence = objectMapper.createArrayNode();
            for (JsonNode e : t.path("evidence")) {
                String quote = e.path("quote").asText("");
                long draftId = e.path("draftId").asLong(-1);
                String draft = drafts.get(draftId);
                // Present in the draft it names, verbatim. Position does not matter here,
                // only that the student wrote it.
                if (draft != null && !quote.isBlank() && quote.length() <= 300 && draft.contains(quote) && evidence.size() < 4) {
                    ObjectNode item = evidence.addObject();
                    item.put("kind", "essay_review");
                    item.put("refId", String.valueOf(draftId));
                    item.put("quote", quote);
                }
            }
            if (!evidence.isEmpty()) {
                kept.add(new Theme(truncate(title, 120), truncate(summary, 1000), traits, evidence));
            }
        }
        return kept;
    }

    /** accepted or dismissed. Dismissing drops the theme's resonance rows; accepting keeps the theme on regeneration. */
    public Map<String, Object> decideTheme(long userId, long themeId, JsonNode body) {
        DeskInput in = new DeskInput(body, Set.of("status"));
        String status = in.oneOf("status", Set.of("accepted", "dismissed"), true);
        int rows = jdbc.update("UPDATE desk.user_theme SET status = ?, decided_at = now() WHERE id = ? AND user_id = ?",
                status, themeId, userId);
        if (rows == 0) {
            throw DeskException.notFound();
        }
        if (status.equals("dismissed")) {
            jdbc.update("DELETE FROM desk.entity_resonance WHERE theme_id = ? AND user_id = ?", themeId, userId);
        }
        return narrative(userId, false);
    }

    // ─── Resonance ────────────────────────────────────────────────────────────

    private record School(long id, String name, String programme, String notes) {}

    private record Pair(long themeId, long targetId, int level, String rationale, String basis) {}

    /** Judges every accepted theme against every open school on the list, replacing the previous judgements. */
    public Map<String, Object> generateResonance(long userId) {
        List<Map<String, Object>> themes = jdbc.queryForList("""
                SELECT id, title, summary, array_to_string(traits, ', ') AS traits FROM desk.user_theme
                WHERE user_id = ? AND status = 'accepted' ORDER BY decided_at DESC NULLS LAST, id DESC LIMIT ?
                """, userId, MAX_THEMES_FOR_RESONANCE);
        if (themes.isEmpty()) {
            throw DeskException.badRequest("Accept a theme first: resonance is judged for the themes you have accepted.");
        }
        List<School> schools = jdbc.query("""
                SELECT t.id, coalesce(cu.display_name, t.custom_name) AS name, t.programme_name, t.notes
                FROM desk.target_entity t
                LEFT JOIN warehouse.canonical_university cu ON cu.canonical_university_id = t.canonical_university_id
                WHERE t.user_id = ? AND t.stage NOT IN ('rejected', 'withdrawn')
                ORDER BY t.deadline NULLS LAST, t.id LIMIT ?
                """, (rs, n) -> new School(rs.getLong("id"), rs.getString("name"), rs.getString("programme_name"),
                        rs.getString("notes")), userId, MAX_TARGETS_FOR_RESONANCE);
        if (schools.isEmpty()) {
            throw DeskException.badRequest("Add a school to your list first.");
        }

        StringBuilder input = new StringBuilder("<themes>\n");
        for (Map<String, Object> t : themes) {
            input.append("- id ").append(t.get("id")).append(": ").append(t.get("title")).append(". ")
                    .append(t.get("summary")).append(" Traits: ").append(t.get("traits")).append("\n");
        }
        input.append("</themes>\n\n<schools>\n");
        for (School s : schools) {
            input.append("- id ").append(s.id()).append(": ").append(s.name());
            if (s.programme() != null) input.append(" (").append(s.programme()).append(")");
            input.append(hasNotes(s) ? "\n  Student's notes: " + truncate(s.notes().trim(), 1000) : "\n  No notes from the student.");
            input.append("\n");
        }
        input.append("</schools>");

        Set<Long> themeIds = new java.util.HashSet<>();
        themes.forEach(t -> themeIds.add(((Number) t.get("id")).longValue()));
        Map<Long, School> byId = new LinkedHashMap<>();
        schools.forEach(s -> byId.put(s.id(), s));

        Reply<List<Pair>> reply = completeJson(resonancePrompt, input.toString(), root -> parsePairs(root, themeIds, byId));
        if (reply.value().isEmpty()) {
            throw new UnreadableReplyException("The model returned no usable resonance levels, so nothing was stored. Try again.");
        }

        tx.executeWithoutResult(status -> {
            jdbc.update("DELETE FROM desk.entity_resonance WHERE user_id = ? AND theme_id = ANY (?)", ps -> {
                ps.setLong(1, userId);
                ps.setArray(2, ps.getConnection().createArrayOf("bigint", themeIds.toArray()));
            });
            for (Pair p : reply.value()) {
                jdbc.update("""
                        INSERT INTO desk.entity_resonance
                            (user_id, theme_id, target_entity_id, level, rationale, institution_basis, model_name, prompt_version)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, userId, p.themeId(), p.targetId(), p.level(), p.rationale(), p.basis(),
                        reply.modelName(), RESONANCE_PROMPT_VERSION);
            }
        });
        Map<String, Object> out = narrative(userId, false);
        out.put("missingPairs", themeIds.size() * schools.size() - reply.value().size());
        return out;
    }

    private List<Pair> parsePairs(JsonNode root, Set<Long> themeIds, Map<Long, School> schools) {
        JsonNode items = root.path("resonance");
        if (!items.isArray()) {
            throw new UnreadableReplyException("\"resonance\" was missing or not a list.");
        }
        Map<String, Pair> pairs = new LinkedHashMap<>();
        for (JsonNode r : items) {
            long themeId = r.path("themeId").asLong(-1);
            long targetId = r.path("targetEntityId").asLong(-1);
            JsonNode level = r.path("level");
            String rationale = r.path("rationale").asText("").trim();
            School school = schools.get(targetId);
            if (!themeIds.contains(themeId) || school == null || !level.isIntegralNumber()
                    || level.asInt() < 1 || level.asInt() > 5 || rationale.isEmpty()) {
                continue;
            }
            // Only a school the student wrote notes about can be judged "from your notes".
            String basis = hasNotes(school) && "user_notes".equals(r.path("basis").asText())
                    ? "user_notes" : "model_general_knowledge";
            pairs.putIfAbsent(themeId + "/" + targetId,
                    new Pair(themeId, targetId, level.asInt(), truncate(rationale, 1000), basis));
        }
        return new ArrayList<>(pairs.values());
    }

    private static boolean hasNotes(School s) {
        return s.notes() != null && !s.notes().isBlank();
    }

    // ─── Model call ───────────────────────────────────────────────────────────

    private record Reply<T>(T value, String modelName) {}

    /** One retry, with the problem named, when the reply is not the JSON asked for. */
    private <T> Reply<T> completeJson(String system, String user, Function<JsonNode, T> parse) {
        DeskModelClient.Reply first = model.complete(system, user);
        try {
            return new Reply<>(parse.apply(ModelJson.readObject(objectMapper, first.text())), first.modelName());
        } catch (UnreadableReplyException problem) {
            DeskModelClient.Reply second = model.complete(system, user + "\n\nYour previous reply could not be used: "
                    + problem.getMessage() + " Reply again with only the JSON object described in the instructions.");
            try {
                return new Reply<>(parse.apply(ModelJson.readObject(objectMapper, second.text())), second.modelName());
            } catch (UnreadableReplyException again) {
                throw new UnreadableReplyException("The model's reply could not be read, so nothing was stored. Try again.");
            }
        }
    }

    private JsonNode parse(String json) {
        try {
            return objectMapper.readTree(json);
        } catch (Exception e) {
            return objectMapper.createArrayNode();
        }
    }

    private static String truncate(String value, int max) {
        return value.length() <= max ? value : value.substring(0, max);
    }

    private static String readResource(String resource) {
        try (InputStream in = new ClassPathResource(resource).getInputStream()) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot read " + resource, e);
        }
    }
}
