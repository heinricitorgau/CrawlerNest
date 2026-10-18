package clawer.desk.essay;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Asks the model to score a draft and turns its reply into something safe to
 * store and show.
 *
 * <p>The model is not trusted to point into the text. It returns quotes; this
 * class finds each quote in the draft and records the offsets itself. A quote
 * that is not in the draft verbatim, or that occurs more than once, is dropped
 * rather than highlighted at a guessed position -- a model that "quotes" a
 * sentence the student never wrote is exactly the failure this guards against.
 *
 * <p>Structural problems (not JSON, a dimension missing, a score out of range)
 * get one retry with the problem named, then a refusal. Nothing partial is stored.
 */
@Component
public class EssayEvaluator {

    static final int MAX_RATIONALE = 800;
    static final int MAX_SUGGESTIONS = 8;
    static final int MAX_SUGGESTED = 1200;
    static final int MAX_REASON = 500;

    public record Span(int start, int end) {}

    public record DimensionScore(int score, String rationale, List<Span> evidence) {}

    public record Suggestion(int start, int end, String original, String suggested, String dimension, String reason) {}

    /**
     * @param droppedQuotes evidence quotes and suggestions discarded because they
     *                      could not be found in the draft exactly once
     */
    public record Evaluation(Map<String, DimensionScore> dimensions, List<Suggestion> suggestions,
                             int droppedQuotes, String modelName) {
        public Map<String, Integer> scores() {
            Map<String, Integer> scores = new LinkedHashMap<>();
            dimensions.forEach((key, value) -> scores.put(key, value.score()));
            return scores;
        }
    }

    /** The model answered, twice, with something that cannot be read as an evaluation. */
    public static class UnreadableReplyException extends RuntimeException {
        public UnreadableReplyException(String message) {
            super(message);
        }
    }

    private final EssayModelClient model;
    private final EssayRubric rubric;
    private final ObjectMapper objectMapper;

    public EssayEvaluator(EssayModelClient model, EssayRubric rubric, ObjectMapper objectMapper) {
        this.model = model;
        this.rubric = rubric;
        this.objectMapper = objectMapper;
    }

    public Evaluation evaluate(String draft, String essayPrompt) {
        String userPrompt = userPrompt(draft, essayPrompt);
        EssayModelClient.Reply reply = model.complete(rubric.systemPrompt(), userPrompt);
        try {
            return parse(reply.text(), draft, reply.modelName());
        } catch (UnreadableReplyException first) {
            String retry = userPrompt + "\n\nYour previous reply could not be used: " + first.getMessage()
                    + " Reply again with only the JSON object described in the instructions.";
            EssayModelClient.Reply second = model.complete(rubric.systemPrompt(), retry);
            try {
                return parse(second.text(), draft, second.modelName());
            } catch (UnreadableReplyException again) {
                throw new UnreadableReplyException(
                        "The model's evaluation could not be read, so nothing was stored. Try again.");
            }
        }
    }

    static String userPrompt(String draft, String essayPrompt) {
        StringBuilder sb = new StringBuilder();
        if (essayPrompt != null && !essayPrompt.isBlank()) {
            sb.append("The essay answers this prompt:\n<prompt>\n").append(essayPrompt).append("\n</prompt>\n\n");
        }
        sb.append("<essay>\n").append(draft).append("\n</essay>");
        return sb.toString();
    }

    Evaluation parse(String text, String draft, String modelName) {
        JsonNode root = readObject(text);
        JsonNode dims = root.path("dimensions");
        if (!dims.isObject()) {
            throw new UnreadableReplyException("\"dimensions\" was missing or not an object.");
        }
        int[] dropped = {0};
        Map<String, DimensionScore> scores = new LinkedHashMap<>();
        for (String key : rubric.keys()) {
            JsonNode d = dims.path(key);
            JsonNode score = d.path("score");
            if (!score.isNumber() || score.asDouble() != Math.rint(score.asDouble())
                    || score.asInt() < 0 || score.asInt() > 100) {
                throw new UnreadableReplyException("\"" + key + "\" needs a whole-number score from 0 to 100.");
            }
            String rationale = d.path("rationale").asText("").trim();
            if (rationale.isEmpty()) {
                throw new UnreadableReplyException("\"" + key + "\" needs a rationale.");
            }
            List<Span> evidence = new ArrayList<>();
            for (JsonNode quote : d.path("evidence")) {
                anchor(draft, quote.asText("")).ifPresentOrElse(evidence::add, () -> dropped[0]++);
            }
            scores.put(key, new DimensionScore(score.asInt(), truncate(rationale, MAX_RATIONALE), evidence));
        }

        List<Suggestion> suggestions = new ArrayList<>();
        for (JsonNode s : root.path("suggestions")) {
            if (suggestions.size() == MAX_SUGGESTIONS) break;
            String original = s.path("original").asText("");
            String suggested = s.path("suggested").asText("").trim();
            String dimension = s.path("dimension").asText("");
            Optional<Span> span = anchor(draft, original);
            if (span.isEmpty() || suggested.isEmpty() || !rubric.keys().contains(dimension)) {
                dropped[0]++;
                continue;
            }
            suggestions.add(new Suggestion(span.get().start(), span.get().end(), original,
                    truncate(suggested, MAX_SUGGESTED), dimension, truncate(s.path("reason").asText("").trim(), MAX_REASON)));
        }
        return new Evaluation(scores, suggestions, dropped[0], modelName);
    }

    /** The quote's position in the draft, only if it occurs there exactly once. */
    static Optional<Span> anchor(String draft, String quote) {
        if (quote == null || quote.isBlank()) {
            return Optional.empty();
        }
        int first = draft.indexOf(quote);
        if (first < 0 || draft.indexOf(quote, first + 1) >= 0) {
            return Optional.empty();
        }
        return Optional.of(new Span(first, first + quote.length()));
    }

    /** The JSON object in the reply, tolerating a Markdown fence or a sentence around it. */
    private JsonNode readObject(String text) {
        if (text == null) {
            throw new UnreadableReplyException("The reply was empty.");
        }
        int open = text.indexOf('{');
        int close = text.lastIndexOf('}');
        if (open < 0 || close < open) {
            throw new UnreadableReplyException("The reply contained no JSON object.");
        }
        try {
            JsonNode node = objectMapper.readTree(text.substring(open, close + 1));
            if (!node.isObject()) {
                throw new UnreadableReplyException("The reply was not a JSON object.");
            }
            return node;
        } catch (UnreadableReplyException e) {
            throw e;
        } catch (Exception e) {
            throw new UnreadableReplyException("The reply was not valid JSON.");
        }
    }

    private static String truncate(String value, int max) {
        return value.length() <= max ? value : value.substring(0, max);
    }
}
