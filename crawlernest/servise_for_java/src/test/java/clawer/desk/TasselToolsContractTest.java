package clawer.desk;

import clawer.desk.service.DeskTargetService;
import clawer.desk.service.DeskTaskService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Tassel's tool definitions (crawlernest-web/src/lib/tassel/tools.json) offer the
 * model exactly the values the desk endpoints accept.
 *
 * <p>If the schema offered a stage the API refuses, the model would be told it
 * may do something every attempt at which fails; if the API accepted one the
 * schema omits, the model could never use it. Both directions are checked.
 */
class TasselToolsContractTest {

    /** Maven runs tests from the module directory; CI checks out the whole repository. */
    private static final Path TOOLS = Path.of("..", "crawlernest-web", "src", "lib", "tassel", "tools.json");

    private final ObjectMapper json = new ObjectMapper();

    private JsonNode parameters(String toolName) throws IOException {
        for (JsonNode tool : json.readTree(Files.readString(TOOLS)).path("tools")) {
            if (tool.path("function").path("name").asText().equals(toolName)) {
                return tool.path("function").path("parameters");
            }
        }
        throw new AssertionError("tools.json has no " + toolName);
    }

    private static Set<String> enumWithoutNull(JsonNode property) {
        Set<String> values = new TreeSet<>();
        property.path("enum").forEach(v -> {
            if (!v.isNull()) values.add(v.asText());
        });
        return values;
    }

    @Test
    void targetEnumsMatchTheTargetService() throws IOException {
        JsonNode props = parameters("update_target_list").path("properties");
        assertEquals(new TreeSet<>(DeskTargetService.STAGES), enumWithoutNull(props.path("stage")));
        assertEquals(new TreeSet<>(DeskTargetService.ROUNDS), enumWithoutNull(props.path("applicationRound")));
        assertEquals(new TreeSet<>(DeskTargetService.BANDS), enumWithoutNull(props.path("userBand")));
    }

    @Test
    void taskPrioritiesMatchTheTaskService() throws IOException {
        JsonNode props = parameters("create_action_task").path("properties");
        assertEquals(new TreeSet<>(DeskTaskService.PRIORITIES), enumWithoutNull(props.path("priority")));
    }

    @Test
    void theToolNamesAreTheDatabaseAllowList() throws IOException {
        Set<String> names = new HashSet<>();
        json.readTree(Files.readString(TOOLS)).path("tools").forEach(t -> names.add(t.path("function").path("name").asText()));

        String sql;
        try (InputStream in = new ClassPathResource("db/auth/V004__tassel_tool_allow_list.sql").getInputStream()) {
            sql = new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
        Matcher list = Pattern.compile("tool_name IN \\(([^)]*)\\)").matcher(sql);
        assertTrue(list.find(), "V004 has no tool_name IN (...) list");
        Set<String> allowed = new HashSet<>();
        Matcher name = Pattern.compile("'([a-z_]+)'").matcher(list.group(1));
        while (name.find()) allowed.add(name.group(1));

        assertEquals(allowed, names);
    }
}
