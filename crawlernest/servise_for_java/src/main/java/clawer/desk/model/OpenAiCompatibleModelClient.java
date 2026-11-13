package clawer.desk.model;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import clawer.auth.jwt.AuthenticatedUser;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Locale;

/**
 * Calls an OpenAI-compatible {@code /chat/completions} endpoint: OpenAI itself,
 * or Ollama's {@code /v1} surface. Configured from the same
 * environment variables as the Next.js agent route (application.properties).
 *
 * <p>"mock" -- the default -- is not a model. Essay scores from a canned reply
 * would be invented numbers presented as an evaluation, so with no real model
 * configured this refuses and the endpoint answers 503.
 *
 * <p>Provider errors are not passed on: their bodies can echo the request,
 * including the essay, or name the account.
 *
 * <p>Every request sent to the provider is written to {@link ModelUsageLedger} with its outcome and the provider's
 * token figures, against the signed-in user of the request that caused it. That is what the day's model budget is
 * counted from, so the budget counts calls actually made, not the most a request might have made.
 */
@Component
public class OpenAiCompatibleModelClient implements DeskModelClient {

    private final String provider;
    private final String model;
    private final String baseUrl;
    private final String apiKey;
    private final Duration timeout;
    /** Sent as reasoning_effort when set; blank sends nothing, which models without the parameter need. */
    private final String reasoningEffort;
    private final ObjectMapper objectMapper;
    private final HttpClient http;
    /** Null in tests that build the client by hand: then nothing is recorded. */
    private final ModelUsageLedger ledger;

    /** Without a ledger: calls are made and not recorded. For tests of what goes on the wire. */
    public OpenAiCompatibleModelClient(String provider, String model, String baseUrl, String ollamaBaseUrl,
                                       String apiKey, Duration timeout, String reasoningEffort,
                                       ObjectMapper objectMapper) {
        this(provider, model, baseUrl, ollamaBaseUrl, apiKey, timeout, reasoningEffort, objectMapper, null);
    }

    @Autowired
    public OpenAiCompatibleModelClient(
            @Value("${crawlernest.model.provider:mock}") String provider,
            @Value("${crawlernest.model.model:}") String model,
            @Value("${crawlernest.model.base-url:}") String baseUrl,
            @Value("${crawlernest.model.ollama-base-url:http://localhost:11434}") String ollamaBaseUrl,
            @Value("${crawlernest.model.api-key:}") String apiKey,
            @Value("${crawlernest.model.timeout:PT60S}") Duration timeout,
            @Value("${crawlernest.model.reasoning-effort:}") String reasoningEffort,
            ObjectMapper objectMapper,
            ModelUsageLedger ledger) {
        this.ledger = ledger;
        this.provider = provider.trim().toLowerCase(Locale.ROOT);
        this.model = model.trim();
        this.baseUrl = switch (this.provider) {
            case "openai" -> withV1(baseUrl.isBlank() ? "https://api.openai.com/v1" : baseUrl);
            case "ollama" -> withV1(baseUrl.isBlank() ? ollamaBaseUrl : baseUrl);
            default -> "";
        };
        this.apiKey = apiKey.trim();
        this.timeout = timeout;
        this.reasoningEffort = reasoningEffort.trim();
        this.objectMapper = objectMapper;
        this.http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
    }

    /** Null when usable; otherwise why not, in words a user can be shown. */
    String configurationProblem() {
        return switch (provider) {
            case "mock" -> "No model is configured, so this cannot run. Nothing was stored.";
            case "openai" -> apiKey.isEmpty() || model.isEmpty()
                    ? "The model is not fully configured. Nothing was stored." : null;
            case "ollama" -> model.isEmpty() ? "The model is not fully configured. Nothing was stored." : null;
            default -> "The model provider setting is not recognised. Nothing was stored.";
        };
    }

    @Override
    public Reply complete(String systemPrompt, String userPrompt) {
        ObjectNode body = baseBody(0.0);
        ArrayNode messages = body.putArray("messages");
        messages.addObject().put("role", "system").put("content", systemPrompt);
        messages.addObject().put("role", "user").put("content", userPrompt);
        if (provider.equals("openai") || provider.equals("ollama")) {
            // Both honour JSON mode.
            body.putObject("response_format").put("type", "json_object");
        }
        JsonNode json = post(body);
        String text = json.path("choices").path(0).path("message").path("content").asText("");
        return new Reply(text, servedModel(json));
    }

    @Override
    public ChatTurn chat(ArrayNode messages, JsonNode tools) {
        // A little warmth for conversation; scoring stays at 0.
        ObjectNode body = baseBody(0.3);
        body.set("messages", messages);
        body.set("tools", tools);
        body.put("tool_choice", "auto");
        JsonNode json = post(body);
        JsonNode message = json.path("choices").path(0).path("message");
        if (!message.isObject()) {
            throw new UnavailableException("The model's reply could not be read. Nothing was stored.");
        }
        return new ChatTurn(message, servedModel(json));
    }

    private ObjectNode baseBody(double temperature) {
        String problem = configurationProblem();
        if (problem != null) {
            throw new UnavailableException(problem);
        }
        ObjectNode body = objectMapper.createObjectNode();
        body.put("model", model);
        body.put("temperature", temperature);
        if (!reasoningEffort.isEmpty()) {
            body.put("reasoning_effort", reasoningEffort);
        }
        return body;
    }

    private String servedModel(JsonNode json) {
        String served = json.path("model").asText(model);
        return served.isBlank() ? model : served;
    }

    private JsonNode post(ObjectNode body) {
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(baseUrl + "/chat/completions"))
                .timeout(timeout)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body.toString()));
        if (!apiKey.isEmpty()) {
            request.header("Authorization", "Bearer " + apiKey);
        }
        HttpResponse<String> response;
        try {
            response = http.send(request.build(), HttpResponse.BodyHandlers.ofString());
        } catch (IOException e) {
            record(ModelUsageLedger.Outcome.UNREACHABLE, null, null);
            throw new UnavailableException("The model could not be reached. Nothing was stored.");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            record(ModelUsageLedger.Outcome.UNREACHABLE, null, null);
            throw new UnavailableException("The model request was interrupted. Nothing was stored.");
        }
        if (response.statusCode() / 100 != 2) {
            record(ModelUsageLedger.Outcome.PROVIDER_ERROR, null, null);
            throw new UnavailableException("The model returned an error. Nothing was stored.");
        }
        JsonNode json;
        try {
            json = objectMapper.readTree(response.body());
        } catch (IOException e) {
            record(ModelUsageLedger.Outcome.OK, null, null);
            throw new UnavailableException("The model's reply could not be read. Nothing was stored.");
        }
        record(ModelUsageLedger.Outcome.OK, servedModel(json), json.path("usage"));
        return json;
    }

    private void record(ModelUsageLedger.Outcome outcome, String servedModel, JsonNode usage) {
        if (ledger == null) {
            return;
        }
        ledger.record(AuthenticatedUser.currentId(), currentEndpoint(), servedModel != null ? servedModel : model,
                outcome, tokens(usage, "prompt_tokens"), tokens(usage, "completion_tokens"));
    }

    /** The provider's own figure, or null when it sent none: an absent count is unknown, not zero. */
    private static Integer tokens(JsonNode usage, String field) {
        if (usage == null) {
            return null;
        }
        JsonNode value = usage.path(field);
        return value.canConvertToInt() && value.isIntegralNumber() && value.intValue() >= 0 ? value.intValue() : null;
    }

    private static String currentEndpoint() {
        if (RequestContextHolder.getRequestAttributes() instanceof ServletRequestAttributes attributes) {
            return attributes.getRequest().getRequestURI();
        }
        return "(no request)";
    }

    private static String withV1(String url) {
        String trimmed = url.trim().replaceAll("/+$", "");
        return trimmed.endsWith("/v1") ? trimmed : trimmed + "/v1";
    }
}
