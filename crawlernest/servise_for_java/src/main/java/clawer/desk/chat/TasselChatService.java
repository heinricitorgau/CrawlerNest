package clawer.desk.chat;

import clawer.desk.model.DeskModelClient;
import clawer.desk.service.DeskProfileService;
import clawer.desk.support.DeskException;
import clawer.desk.support.DeskInput;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * One turn of the conversation with Tassel: the tool loop.
 *
 * <p>The browser sends the message and the recent history; nothing about the
 * conversation is stored here except the actions. Each turn:
 * <ol>
 *   <li>builds the system prompt (prompts/tassel_system.txt) plus a context
 *       block of the user's own desk -- today in their time zone, open tasks,
 *       schools, essay titles (no scores: Tassel gives none in chat);</li>
 *   <li>calls the model with the tools in prompts/tassel_tools.json;</li>
 *   <li>hands every tool call to {@link TasselToolExecutor}, which validates,
 *       records and applies or proposes it, and returns each result to the
 *       model so its reply is written knowing what actually happened;</li>
 *   <li>repeats until the model answers without a tool call, at most
 *       {@link #MAX_ROUNDS} rounds and {@link #MAX_CALLS_PER_TURN} calls.</li>
 * </ol>
 *
 * <p>The response carries the actions with their statuses next to the reply.
 * The UI draws those as the record of what happened, so a reply that misstates
 * an outcome is contradicted on the same screen.
 */
@Service
public class TasselChatService {

    static final int MAX_MESSAGE = 4000;
    static final int MAX_HISTORY = 20;
    static final int MAX_HISTORY_ITEM = 8000;
    static final int MAX_ROUNDS = 3;
    static final int MAX_CALLS_PER_TURN = 5;
    /** Lookups change nothing, so they have their own, separate cap. */
    static final int MAX_LOOKUPS_PER_TURN = 3;
    static final Set<String> MODES = Set.of("general", "brainstorming", "review");

    private final JdbcTemplate jdbc;
    private final DeskModelClient model;
    private final TasselToolExecutor executor;
    private final TasselFederalLookup federalLookup;
    private final DeskProfileService profiles;
    private final ObjectMapper objectMapper;
    private final String systemPrompt;
    private final JsonNode tools;

    public TasselChatService(JdbcTemplate jdbc, DeskModelClient model, TasselToolExecutor executor,
                             TasselFederalLookup federalLookup, DeskProfileService profiles, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.model = model;
        this.executor = executor;
        this.federalLookup = federalLookup;
        this.profiles = profiles;
        this.objectMapper = objectMapper;
        this.systemPrompt = readResource("prompts/tassel_system.txt").strip();
        try {
            this.tools = objectMapper.readTree(readResource("prompts/tassel_tools.json")).path("tools");
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    public Map<String, Object> message(long userId, JsonNode body) {
        DeskInput in = new DeskInput(body, Set.of("sessionId", "message", "history", "mode"));
        String sessionId = in.text("sessionId", 64, true);
        String message = in.text("message", MAX_MESSAGE, true);
        String mode = in.oneOf("mode", MODES, false);
        List<String[]> history = readHistory(in.node("history"));

        List<String> userMessages = new ArrayList<>();
        ArrayNode messages = objectMapper.createArrayNode();
        messages.addObject().put("role", "system").put("content", systemPrompt + "\n\n" + context(userId, mode == null ? "general" : mode));
        for (String[] turn : history) {
            messages.addObject().put("role", turn[0]).put("content", turn[1]);
            if (turn[0].equals("user")) userMessages.add(turn[1]);
        }
        messages.addObject().put("role", "user").put("content", message);
        userMessages.add(message);

        int turnIndex = history.size();
        List<TasselToolExecutor.Outcome> actions = new ArrayList<>();
        List<TasselFederalLookup.Result> lookups = new ArrayList<>();
        String modelName = null;
        String reply = "";
        boolean stoppedEarly = false;

        for (int round = 0; ; round++) {
            DeskModelClient.ChatTurn turn = model.chat(messages, tools);
            modelName = turn.modelName();
            JsonNode assistant = turn.message();
            reply = assistant.path("content").asText("").strip();
            JsonNode calls = assistant.path("tool_calls");
            if (!calls.isArray() || calls.isEmpty()) {
                break;
            }
            if (round == MAX_ROUNDS || actions.size() >= MAX_CALLS_PER_TURN) {
                stoppedEarly = true;
                break;
            }
            // The assistant message goes back as the provider sent it: the tool
            // results that follow must answer its tool_call ids.
            ObjectNode echoed = messages.addObject();
            echoed.put("role", "assistant");
            echoed.put("content", reply);
            echoed.set("tool_calls", calls);
            TasselToolExecutor.Turn context = new TasselToolExecutor.Turn(userId, sessionId, turnIndex, modelName, userMessages);
            for (JsonNode call : calls) {
                String result;
                String name = call.path("function").path("name").asText("");
                if (TasselFederalLookup.TOOL.equals(name)) {
                    if (lookups.size() >= MAX_LOOKUPS_PER_TURN) {
                        result = "{\"status\": \"failed\", \"message\": \"Too many lookups in one turn; answer with what you have.\"}";
                    } else {
                        TasselFederalLookup.Result lookup =
                                federalLookup.lookup(userId, call.path("function").path("arguments").asText(""));
                        lookups.add(lookup);
                        result = lookup.forModel().toString();
                    }
                } else if (actions.size() >= MAX_CALLS_PER_TURN) {
                    result = "{\"status\": \"failed\", \"message\": \"Too many changes in one turn; ask the user to continue.\"}";
                } else {
                    TasselToolExecutor.Outcome outcome = executor.execute(context,
                            name, call.path("function").path("arguments").asText(""));
                    actions.add(outcome);
                    result = executor.toolResultForModel(outcome);
                }
                messages.addObject().put("role", "tool").put("tool_call_id", call.path("id").asText("")).put("content", result);
            }
        }

        if (reply.isEmpty()) {
            reply = actions.isEmpty() ? "Sorry, I have no answer to that. Could you say it another way?"
                    : "Here is what I did:";
        }
        if (stoppedEarly) {
            reply = reply + "\n\n(I stopped after several changes. The list below is everything that happened.)";
        }

        List<Map<String, Object>> writes = new ArrayList<>();
        for (TasselToolExecutor.Outcome o : actions) {
            if (o.status().equals("applied") && o.result() != null) {
                Map<String, Object> w = new LinkedHashMap<>();
                w.put("table", "desk." + o.result().path("table").asText());
                w.put("id", o.result().has("ids") ? o.result().get("ids") : o.result().get("id"));
                writes.add(w);
            }
        }
        Map<String, Object> disclosure = new LinkedHashMap<>();
        disclosure.put("model", modelName);
        disclosure.put("userDataWrites", writes);
        disclosure.put("warehouseWrites", false);
        // What Tassel read beyond the desk, so a reply quoting a figure can be traced to its record.
        disclosure.put("warehouseReads", lookups.stream().map(TasselChatService::lookupView).toList());
        disclosure.put("pipelineRuns", false);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("turnIndex", turnIndex);
        out.put("reply", Map.of("text", reply, "paragraphs",
                Arrays.stream(reply.split("\\n{2,}")).map(String::strip).filter(p -> !p.isEmpty()).toList()));
        out.put("actions", actions.stream().map(TasselChatService::actionView).toList());
        // The caveats of every figure Tassel read this turn, once each, in the order first read.
        LinkedHashSet<String> caveats = new LinkedHashSet<>();
        lookups.forEach(l -> caveats.addAll(l.caveats()));
        out.put("caveats", List.copyOf(caveats));
        out.put("disclosure", disclosure);
        return out;
    }

    static Map<String, Object> lookupView(TasselFederalLookup.Result l) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("tool", l.tool());
        m.put("status", l.status());
        m.put("targetEntityId", l.targetEntityId());
        m.put("canonicalUniversityId", l.canonicalUniversityId());
        m.put("unitid", l.unitid());
        return m;
    }

    static Map<String, Object> actionView(TasselToolExecutor.Outcome o) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", o.id());
        m.put("tool", o.tool());
        m.put("status", o.status());
        m.put("message", o.message());
        m.put("arguments", o.arguments());
        m.put("result", o.result());
        return m;
    }

    private List<String[]> readHistory(JsonNode node) {
        List<String[]> history = new ArrayList<>();
        if (node == null) return history;
        if (!node.isArray()) throw DeskException.badRequest("history must be a list.");
        if (node.size() > MAX_HISTORY) throw DeskException.badRequest("history must have " + MAX_HISTORY + " turns or fewer.");
        for (JsonNode turn : node) {
            String role = turn.path("role").asText("");
            JsonNode content = turn.path("content");
            if (!(role.equals("user") || role.equals("assistant")) || !content.isTextual()) {
                throw DeskException.badRequest("Each history turn needs role user or assistant and string content.");
            }
            if (content.asText().length() > MAX_HISTORY_ITEM) {
                throw DeskException.badRequest("A history turn is longer than " + MAX_HISTORY_ITEM + " characters.");
            }
            history.add(new String[]{role, content.asText()});
        }
        return history;
    }

    /** The per-turn facts after the fixed prompt. Ids are listed so tools can refer to rows. */
    String context(long userId, String mode) {
        ZoneId zone = profiles.zoneOf(userId);
        StringBuilder sb = new StringBuilder("## Context\n");
        sb.append("Today: ").append(LocalDate.now(zone)).append(" (").append(zone.getId()).append(")\n");
        sb.append("Mode: ").append(mode).append("\n");
        sb.append("Open tasks:\n");
        List<String> tasks = jdbc.query("""
                SELECT id, title, due_date FROM desk.task WHERE user_id = ? AND status IN ('todo', 'in_progress')
                ORDER BY due_date NULLS LAST, id LIMIT 20
                """, (rs, n) -> "- [" + rs.getLong("id") + "] " + rs.getString("title")
                + (rs.getDate("due_date") == null ? "" : " (due " + rs.getDate("due_date").toLocalDate() + ")"), userId);
        sb.append(tasks.isEmpty() ? "- none\n" : String.join("\n", tasks) + "\n");
        sb.append("Target schools (the student's own list and labels):\n");
        List<String> schools = jdbc.query("""
                SELECT t.id, coalesce(cu.display_name, t.custom_name) AS name, t.stage, t.deadline
                FROM desk.target_entity t
                LEFT JOIN warehouse.canonical_university cu ON cu.canonical_university_id = t.canonical_university_id
                WHERE t.user_id = ? ORDER BY t.deadline NULLS LAST, t.id LIMIT 20
                """, (rs, n) -> "- [" + rs.getLong("id") + "] " + rs.getString("name") + ": " + rs.getString("stage")
                + (rs.getDate("deadline") == null ? "" : ", own deadline " + rs.getDate("deadline").toLocalDate()), userId);
        sb.append(schools.isEmpty() ? "- none\n" : String.join("\n", schools) + "\n");
        sb.append("Essay reviews on file (scores are on the Essay review tab, not here):\n");
        List<String> essays = jdbc.query("""
                SELECT id, essay_title, created_at FROM desk.essay_review WHERE user_id = ?
                ORDER BY created_at DESC, id DESC LIMIT 10
                """, (rs, n) -> "- [" + rs.getLong("id") + "] " + rs.getString("essay_title") + ", reviewed "
                + rs.getTimestamp("created_at").toInstant().atZone(zone).toLocalDate(), userId);
        sb.append(essays.isEmpty() ? "- none" : String.join("\n", essays));
        return sb.toString();
    }

    private static String readResource(String resource) {
        try (InputStream in = new ClassPathResource(resource).getInputStream()) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot read " + resource, e);
        }
    }
}
