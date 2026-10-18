package clawer.desk.essay;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * The essay rubric, read from prompts/essay_rubric.json: dimensions, their fixed
 * weights and the score bands.
 *
 * <p>The weights live here and nowhere in the model's output. The model scores
 * each dimension; {@link #overall} turns those into the headline number, so the
 * same dimension scores always give the same overall score.
 */
@Component
public class EssayRubric {

    static final String RUBRIC_RESOURCE = "prompts/essay_rubric.json";
    static final String SYSTEM_PROMPT_RESOURCE = "prompts/essay_scoring_system.txt";

    public record Dimension(String key, String label, BigDecimal weight, String definition) {}

    public record Band(int min, int max, String meaning) {}

    private final String version;
    private final List<Dimension> dimensions;
    private final List<Band> bands;
    private final String systemPrompt;

    public EssayRubric(ObjectMapper objectMapper) {
        JsonNode root = readJson(objectMapper, RUBRIC_RESOURCE);
        this.version = root.path("version").asText();
        List<Dimension> dims = new ArrayList<>();
        for (JsonNode d : root.path("dimensions")) {
            dims.add(new Dimension(d.path("key").asText(), d.path("label").asText(),
                    d.path("weight").decimalValue(), d.path("definition").asText()));
        }
        this.dimensions = List.copyOf(dims);
        List<Band> bandList = new ArrayList<>();
        for (JsonNode b : root.path("bands")) {
            bandList.add(new Band(b.path("min").asInt(), b.path("max").asInt(), b.path("meaning").asText()));
        }
        this.bands = List.copyOf(bandList);
        BigDecimal total = dimensions.stream().map(Dimension::weight).reduce(BigDecimal.ZERO, BigDecimal::add);
        if (version.isBlank() || dimensions.isEmpty() || total.compareTo(BigDecimal.ONE) != 0) {
            throw new IllegalStateException(RUBRIC_RESOURCE + " needs a version and dimensions whose weights sum to 1");
        }
        this.systemPrompt = renderSystemPrompt(readText(SYSTEM_PROMPT_RESOURCE));
    }

    public String version() {
        return version;
    }

    public List<Dimension> dimensions() {
        return dimensions;
    }

    public List<String> keys() {
        return dimensions.stream().map(Dimension::key).toList();
    }

    public String systemPrompt() {
        return systemPrompt;
    }

    /** Weighted mean of the dimension scores, to one decimal place. Every key must be present. */
    public BigDecimal overall(Map<String, Integer> scores) {
        BigDecimal sum = BigDecimal.ZERO;
        for (Dimension d : dimensions) {
            Integer score = scores.get(d.key());
            if (score == null) {
                throw new IllegalArgumentException("Missing score for " + d.key());
            }
            sum = sum.add(d.weight().multiply(BigDecimal.valueOf(score)));
        }
        return sum.setScale(1, RoundingMode.HALF_UP);
    }

    public Map<String, BigDecimal> weights() {
        return dimensions.stream().collect(Collectors.toMap(Dimension::key, Dimension::weight,
                (a, b) -> a, java.util.LinkedHashMap::new));
    }

    private String renderSystemPrompt(String template) {
        String dims = dimensions.stream()
                .map(d -> "- " + d.key() + " (" + d.label() + "): " + d.definition())
                .collect(Collectors.joining("\n"));
        String bandText = bands.stream()
                .map(b -> "- " + b.min() + "-" + b.max() + ": " + b.meaning())
                .collect(Collectors.joining("\n"));
        String shape = dimensions.stream()
                .map(d -> "    \"" + d.key() + "\": {\"score\": <0-100>, \"rationale\": \"<1-2 sentences>\", \"evidence\": [\"<verbatim quote>\"]}")
                .collect(Collectors.joining(",\n"));
        return template
                .replace("{{RUBRIC_VERSION}}", version)
                .replace("{{DIMENSIONS}}", dims)
                .replace("{{BANDS}}", bandText)
                .replace("{{DIMENSION_SHAPE}}", shape)
                .replace("{{DIMENSION_KEYS}}", String.join(", ", keys()));
    }

    private static JsonNode readJson(ObjectMapper objectMapper, String resource) {
        try (InputStream in = new ClassPathResource(resource).getInputStream()) {
            return objectMapper.readTree(in);
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot read " + resource, e);
        }
    }

    private static String readText(String resource) {
        try (InputStream in = new ClassPathResource(resource).getInputStream()) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot read " + resource, e);
        }
    }
}
