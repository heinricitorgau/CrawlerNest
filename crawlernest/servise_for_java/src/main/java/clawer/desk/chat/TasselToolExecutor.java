package clawer.desk.chat;

import clawer.desk.service.DeskProfileService;
import clawer.desk.service.DeskTargetService;
import clawer.desk.service.DeskTaskService;
import clawer.desk.story.NarrativeService;
import clawer.desk.support.DeskException;
import clawer.desk.support.DeskInput;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Turns one tool call from the model into what actually happens, and records it.
 *
 * <p>The model proposes; this decides. Every call is validated with the limits
 * the desk forms use (DeskInput, the services' enums and ownership checks), then:
 * <ul>
 *   <li>applied at once -- create_action_task, update_target_list "add",
 *       generate_narrative_themes (stored as suggestions) -- with undo; or</li>
 *   <li>held as "proposed" for the user to confirm -- update_target_list
 *       "update" and "remove", which change something the user already has; or</li>
 *   <li>refused as "failed", with the reason, which the model is told.</li>
 * </ul>
 * Every call with a known tool name gets a desk.chat_action row, failures
 * included. The policy here is the one tassel_tools.json states.
 */
@Component
public class TasselToolExecutor {

    public static final String THEMES_PROMPT_VERSION = "tassel-themes-2026.1";

    /** What one call came to. {@code id} is null only for a tool name the database would not accept. */
    public record Outcome(UUID id, String tool, String status, JsonNode arguments, JsonNode result, String message) {}

    /** What the executor needs to know about the turn, beyond the call itself. */
    public record Turn(long userId, String sessionId, int turnIndex, String modelName, List<String> userMessages) {}

    private static final Set<String> TOOLS = Set.of("update_target_list", "create_action_task", "generate_narrative_themes");

    private final JdbcTemplate jdbc;
    private final TransactionTemplate tx;
    private final ObjectMapper objectMapper;
    private final DeskTaskService tasks;
    private final DeskTargetService targets;
    private final DeskProfileService profiles;
    private final NarrativeService narrative;

    public TasselToolExecutor(JdbcTemplate jdbc, TransactionTemplate tx, ObjectMapper objectMapper, DeskTaskService tasks,
                              DeskTargetService targets, DeskProfileService profiles, NarrativeService narrative) {
        this.jdbc = jdbc;
        this.tx = tx;
        this.objectMapper = objectMapper;
        this.tasks = tasks;
        this.targets = targets;
        this.profiles = profiles;
        this.narrative = narrative;
    }

    public Outcome execute(Turn turn, String toolName, String rawArguments) {
        if (!TOOLS.contains(toolName)) {
            return new Outcome(null, toolName, "failed", objectMapper.createObjectNode(), null,
                    "There is no tool called " + toolName + ".");
        }
        JsonNode args;
        try {
            args = objectMapper.readTree(rawArguments == null || rawArguments.isBlank() ? "{}" : rawArguments);
        } catch (Exception e) {
            args = null;
        }
        if (args == null || !args.isObject()) {
            return fail(turn, toolName, objectMapper.createObjectNode(), "The arguments were not a JSON object.");
        }
        JsonNode arguments = args;
        try {
            return switch (toolName) {
                case "create_action_task" -> createTask(turn, arguments);
                case "update_target_list" -> updateTargets(turn, arguments);
                default -> generateThemes(turn, arguments);
            };
        } catch (DeskException e) {
            return fail(turn, toolName, arguments, e.getMessage());
        } catch (DataAccessException e) {
            return fail(turn, toolName, arguments, "The change conflicts with the user's existing data.");
        }
    }

    // ─── create_action_task ───────────────────────────────────────────────────

    private Outcome createTask(Turn turn, JsonNode args) {
        DeskInput in = new DeskInput(args, Set.of("title", "dueDate", "priority", "category", "targetEntityId", "sourceQuote"));
        String title = in.text("title", 200, true);
        LocalDate dueDate = in.date("dueDate", false);
        String priority = in.oneOf("priority", DeskTaskService.PRIORITIES, false);
        String category = in.text("category", 40, false);
        Long targetEntityId = in.id("targetEntityId", false);
        in.text("sourceQuote", 300, true);
        LocalDate today = LocalDate.now(profiles.zoneOf(turn.userId()));
        if (dueDate != null && dueDate.isBefore(today)) {
            throw DeskException.badRequest("The due date " + dueDate + " is in the past (today is " + today + ").");
        }
        UUID id = UUID.randomUUID();
        DeskTaskService.Task task = tx.execute(status -> {
            insertAction(id, turn, "create_action_task", args, "applied", null);
            DeskTaskService.Task created = tasks.createForAgent(turn.userId(), title, dueDate, priority, category, targetEntityId, id);
            setResult(id, result("task", created.id()));
            return created;
        });
        return new Outcome(id, "create_action_task", "applied", args, result("task", task.id()),
                "Added the task \"" + task.title() + "\"" + (task.dueDate() == null ? "" : ", due " + task.dueDate()) + ".");
    }

    // ─── update_target_list ───────────────────────────────────────────────────

    private static final Set<String> TARGET_FIELDS = Set.of("action", "targetEntityId", "universityName", "programmeName",
            "stage", "applicationRound", "deadline", "userBand", "reason");

    private Outcome updateTargets(Turn turn, JsonNode args) {
        DeskInput in = new DeskInput(args, TARGET_FIELDS);
        String action = in.oneOf("action", Set.of("add", "update", "remove"), true);
        in.text("reason", 300, true);
        String stage = in.oneOf("stage", DeskTargetService.STAGES, false);
        String round = in.oneOf("applicationRound", DeskTargetService.ROUNDS, false);
        String band = in.oneOf("userBand", DeskTargetService.BANDS, false);
        LocalDate deadline = in.date("deadline", false);
        String programme = in.text("programmeName", 200, false);

        if (action.equals("add")) {
            String name = in.text("universityName", 200, true).replaceAll("\\s+", " ");
            if (deadline != null && deadline.isBefore(LocalDate.now(profiles.zoneOf(turn.userId())))) {
                throw DeskException.badRequest("The deadline " + deadline + " is in the past.");
            }
            Long canonicalId = exactUniversityMatch(name);
            UUID id = UUID.randomUUID();
            DeskTargetService.Target target = tx.execute(status -> {
                insertAction(id, turn, "update_target_list", args, "applied", null);
                DeskTargetService.Target created = targets.createForAgent(turn.userId(), canonicalId,
                        canonicalId == null ? name : null, programme, stage, round, band, deadline);
                setResult(id, targetResult(created));
                return created;
            });
            return new Outcome(id, "update_target_list", "applied", args, targetResult(target),
                    "Added " + target.name() + " to the list"
                            + (canonicalId == null ? ", under the name the user gave (no exact match in CrawlerNest's records)." : "."));
        }

        Long targetId = in.id("targetEntityId", true);
        DeskTargetService.Target target = targets.find(turn.userId(), targetId)
                .orElseThrow(() -> DeskException.badRequest("There is no school with id " + targetId + " on the user's list."));
        if (action.equals("update") && stage == null && round == null && deadline == null && band == null) {
            throw DeskException.badRequest("An update needs at least one of stage, applicationRound, deadline or userBand.");
        }
        UUID id = UUID.randomUUID();
        ObjectNode result = targetResult(target);
        insertAction(id, turn, "update_target_list", args, "proposed", result);
        String what = action.equals("remove") ? "remove " + target.name() + " from the list" : "update " + target.name();
        return new Outcome(id, "update_target_list", "proposed", args, result,
                "Proposed to " + what + ". It waits for the user to confirm it on the desk.");
    }

    /**
     * The warehouse university this name means, only when the name equals one
     * active university's display name, native name or alias (ignoring case and
     * spacing) and no other. The one allowance: a trailing all-caps parenthetical
     * on the display name is ignored, so "Massachusetts Institute of Technology"
     * finds "Massachusetts Institute of Technology (MIT)" -- the same narrow rule
     * the name normaliser applies, and stripping it collides no two active records.
     * Nothing beyond that and no fuzzy tier: the repo's normaliser treats
     * "Miami University" and "University of Miami" alike (CLAUDE.md, entity
     * resolution traps), and a wrong link is worse than keeping the user's words.
     */
    Long exactUniversityMatch(String name) {
        Boolean hasAliases = jdbc.queryForObject("SELECT to_regclass('warehouse.university_alias') IS NOT NULL", Boolean.class);
        String aliasClause = Boolean.TRUE.equals(hasAliases)
                ? " OR cu.canonical_university_id IN (SELECT canonical_university_id FROM warehouse.university_alias"
                  + " WHERE lower(regexp_replace(trim(alias_text), '\\s+', ' ', 'g')) = lower(?))"
                : "";
        String sql = "SELECT DISTINCT cu.canonical_university_id FROM warehouse.canonical_university cu WHERE cu.status = 'active'"
                + " AND (lower(regexp_replace(trim(cu.display_name), '\\s+', ' ', 'g')) = lower(?)"
                + " OR lower(regexp_replace(regexp_replace(trim(cu.display_name), '\\s*\\([A-Z0-9]{1,10}\\)$', ''), '\\s+', ' ', 'g')) = lower(?)"
                + " OR lower(regexp_replace(trim(coalesce(cu.native_name, '')), '\\s+', ' ', 'g')) = lower(?)" + aliasClause + ")"
                + " LIMIT 2";
        List<Long> ids = Boolean.TRUE.equals(hasAliases)
                ? jdbc.queryForList(sql, Long.class, name, name, name, name)
                : jdbc.queryForList(sql, Long.class, name, name, name);
        return ids.size() == 1 ? ids.get(0) : null;
    }

    /** Applies a confirmed update/remove proposal. Throws DeskException when it can no longer be applied. */
    JsonNode applyProposal(long userId, JsonNode args) {
        long targetId = args.path("targetEntityId").asLong();
        if (args.path("action").asText().equals("remove")) {
            if (!targets.delete(userId, targetId)) {
                throw DeskException.badRequest("That school is no longer on the list.");
            }
            ObjectNode r = objectMapper.createObjectNode();
            r.put("table", "target_entity");
            r.put("id", targetId);
            r.put("removed", true);
            return r;
        }
        ObjectNode patch = objectMapper.createObjectNode();
        for (String field : List.of("stage", "applicationRound", "deadline", "userBand")) {
            if (args.hasNonNull(field)) patch.set(field, args.get(field));
        }
        return targetResult(targets.update(userId, targetId, patch));
    }

    // ─── generate_narrative_themes ────────────────────────────────────────────

    private Outcome generateThemes(Turn turn, JsonNode args) {
        new DeskInput(args, Set.of("themes"));
        JsonNode themes = args.path("themes");
        if (!themes.isArray() || themes.isEmpty()) {
            throw DeskException.badRequest("themes must be a list of one or two themes.");
        }
        List<NarrativeService.Theme> kept = new ArrayList<>();
        int dropped = 0;
        for (JsonNode t : themes) {
            if (kept.size() == 2) break;
            String title = t.path("title").asText("").trim();
            String summary = t.path("summary").asText("").trim();
            if (title.isEmpty() || summary.isEmpty() || title.length() > 120 || summary.length() > 1000) {
                dropped++;
                continue;
            }
            List<String> traits = new ArrayList<>();
            for (JsonNode trait : t.path("traits")) {
                String text = trait.asText("").trim();
                if (!text.isEmpty() && text.length() <= 40 && traits.size() < 5) traits.add(text);
            }
            ArrayNode evidence = objectMapper.createArrayNode();
            for (JsonNode e : t.path("evidence")) {
                String quote = e.path("quote").asText("");
                String kind = e.path("sourceKind").asText("");
                String ref = e.path("sourceRef").isNull() ? null : e.path("sourceRef").asText(null);
                if (quote.isBlank() || quote.length() > 300 || evidence.size() >= 6 || !quoteIsTheUsers(turn, kind, ref, quote)) {
                    dropped++;
                    continue;
                }
                ObjectNode item = evidence.addObject();
                item.put("kind", kind);
                if (ref != null) item.put("refId", ref);
                item.put("quote", quote);
            }
            if (!evidence.isEmpty()) {
                kept.add(new NarrativeService.Theme(title, summary, traits, evidence));
            }
        }
        if (kept.isEmpty()) {
            throw DeskException.badRequest("No theme could be tied to quotes from the user's own messages or essays, so none was saved.");
        }
        UUID id = UUID.randomUUID();
        int droppedQuotes = dropped;
        List<Long> ids = tx.execute(status -> {
            insertAction(id, turn, "generate_narrative_themes", args, "applied", null);
            List<Long> stored = narrative.storeSuggestedThemes(turn.userId(), kept, turn.modelName(), THEMES_PROMPT_VERSION);
            setResult(id, themesResult(stored, droppedQuotes));
            return stored;
        });
        return new Outcome(id, "generate_narrative_themes", "applied", args, themesResult(ids, droppedQuotes),
                "Saved " + ids.size() + " theme(s) as suggestions; the user can keep or dismiss each on the desk."
                        + (droppedQuotes > 0 ? " " + droppedQuotes + " quote(s) or theme(s) could not be found in the user's own words and were left out." : ""));
    }

    /** A chat quote must be in one of the user's own messages; an essay quote in a draft the user owns. */
    private boolean quoteIsTheUsers(Turn turn, String kind, String ref, String quote) {
        if (kind.equals("chat_message")) {
            return turn.userMessages().stream().anyMatch(m -> m.contains(quote));
        }
        if (kind.equals("essay_review") && ref != null && ref.matches("\\d{1,18}")) {
            List<String> draft = jdbc.queryForList("SELECT draft_text FROM desk.essay_review WHERE id = ? AND user_id = ?",
                    String.class, Long.parseLong(ref), turn.userId());
            return !draft.isEmpty() && draft.get(0).contains(quote);
        }
        return false;
    }

    // ─── Recording ────────────────────────────────────────────────────────────

    private Outcome fail(Turn turn, String tool, JsonNode args, String message) {
        UUID id = UUID.randomUUID();
        ObjectNode result = objectMapper.createObjectNode();
        result.put("error", message);
        insertAction(id, turn, tool, args, "failed", result);
        return new Outcome(id, tool, "failed", args, result, message);
    }

    private void insertAction(UUID id, Turn turn, String tool, JsonNode args, String status, JsonNode result) {
        jdbc.update("""
                INSERT INTO desk.chat_action (id, user_id, session_id, turn_index, tool_name, arguments, status, result, model_name)
                VALUES (?, ?, ?, ?, ?, ?::jsonb, ?, ?::jsonb, ?)
                """, id, turn.userId(), turn.sessionId(), turn.turnIndex(), tool, args.toString(), status,
                result == null ? null : result.toString(), turn.modelName());
    }

    private void setResult(UUID id, JsonNode result) {
        jdbc.update("UPDATE desk.chat_action SET result = ?::jsonb WHERE id = ?", result.toString(), id);
    }

    private ObjectNode result(String table, long rowId) {
        ObjectNode r = objectMapper.createObjectNode();
        r.put("table", table);
        r.put("id", rowId);
        return r;
    }

    private ObjectNode targetResult(DeskTargetService.Target t) {
        ObjectNode r = result("target_entity", t.id());
        r.put("name", t.name());
        r.put("linkedToUniversity", t.canonicalUniversityId() != null);
        r.put("stage", t.stage());
        return r;
    }

    private ObjectNode themesResult(List<Long> ids, int dropped) {
        ObjectNode r = objectMapper.createObjectNode();
        r.put("table", "user_theme");
        ArrayNode list = r.putArray("ids");
        ids.forEach(list::add);
        r.put("droppedQuotes", dropped);
        return r;
    }

    /** The message the model gets back for a call: status first, so it cannot misreport it. */
    public String toolResultForModel(Outcome o) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("status", o.status());
        m.put("message", o.message());
        if (o.result() != null && o.result().has("id")) m.put("id", o.result().get("id"));
        try {
            return objectMapper.writeValueAsString(m);
        } catch (Exception e) {
            return "{\"status\": \"" + o.status() + "\"}";
        }
    }
}
