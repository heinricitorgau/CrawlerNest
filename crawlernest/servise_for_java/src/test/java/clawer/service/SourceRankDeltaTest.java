package clawer.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * SourceRankDelta against the golden cases {@code test_rank_delta.py} also asserts,
 * so the Java and Python rules cannot drift apart.
 */
class SourceRankDeltaTest {

    private static final Path GOLDEN = Path.of("..", "crawlernest-tests", "fixtures", "rank_delta_cases.json");

    private static Integer intOrNull(JsonNode node) {
        return node == null || node.isNull() ? null : node.asInt();
    }

    private static String textOrNull(JsonNode node) {
        return node == null || node.isNull() ? null : node.asText();
    }

    @TestFactory
    Stream<DynamicTest> goldenCasesMatchPython() throws IOException {
        JsonNode golden = new ObjectMapper().readTree(Files.readString(GOLDEN));
        List<InstitutionLineage.Event> lineage = new ArrayList<>();
        golden.get("lineage").forEach(e -> lineage.add(new InstitutionLineage.Event(
                e.get("predecessor").asLong(), e.get("successor").asLong(),
                e.get("effective_year").asInt(), e.get("kind").asText())));

        List<DynamicTest> tests = new ArrayList<>();
        golden.get("cases").forEach(c -> tests.add(DynamicTest.dynamicTest(c.get("name").asText(), () -> {
            List<Integer> held = new ArrayList<>();
            c.get("held").forEach(y -> held.add(y.asInt()));
            int priorYear = c.get("prior_year").asInt();
            SourceRankDelta.Observation current = new SourceRankDelta.Observation(
                    2026, c.get("source").asText(), c.get("current").asText(), textOrNull(c.get("current_id")), false);
            SourceRankDelta.Observation prior = c.get("prior").isNull() ? null : new SourceRankDelta.Observation(
                    priorYear, c.get("source").asText(), c.get("prior").asText(), textOrNull(c.get("prior_id")),
                    c.has("prior_suspicious") && c.get("prior_suspicious").asBoolean());

            SourceRankDelta.Result result = SourceRankDelta.compute(
                    current, prior, priorYear, c.get("university").asLong(), lineage, held);

            JsonNode expect = c.get("expect");
            assertEquals(intOrNull(expect.get("value")), result.value(), "value");
            assertEquals(intOrNull(expect.get("min")), result.min(), "min");
            assertEquals(intOrNull(expect.get("max")), result.max(), "max");
            assertEquals(textOrNull(expect.get("direction")), result.direction(), "direction");
            assertEquals(textOrNull(expect.get("reason")), result.reason(), "reason");
        })));
        return tests.stream();
    }

    @Test
    void aRowWhosePrintedRankIsUnknownIsWithheldNotReadFromRankPosition() {
        SourceRankDelta.Result result = SourceRankDelta.compute(
                new SourceRankDelta.Observation(2026, "QS", null, "q", false),
                new SourceRankDelta.Observation(2025, "QS", "17", "q", false),
                2025, 1L, List.of(), List.of(2026, 2025));
        assertEquals(SourceRankDelta.REASON_RANK_DISPLAY_MISSING, result.reason());
        assertNull(result.direction());
    }

    @Test
    void sourcesAreNeverCompared() {
        assertThrows(IllegalArgumentException.class, () -> SourceRankDelta.compute(
                new SourceRankDelta.Observation(2026, "QS", "14", "q", false),
                new SourceRankDelta.Observation(2025, "THE", "14", "t", false),
                2025, 1L, List.of(), List.of(2026, 2025)));
    }
}
