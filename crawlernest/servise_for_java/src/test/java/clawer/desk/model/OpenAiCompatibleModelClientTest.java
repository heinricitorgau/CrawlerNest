package clawer.desk.model;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * What the client puts on the wire, against a local stand-in for an
 * OpenAI-compatible server. No network, no model.
 */
class OpenAiCompatibleModelClientTest {

    private final ObjectMapper json = new ObjectMapper();
    private final List<JsonNode> requests = new ArrayList<>();
    private HttpServer server;
    private int status = 200;

    @BeforeEach
    void start() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/v1/chat/completions", exchange -> {
            requests.add(json.readTree(exchange.getRequestBody()));
            byte[] body = "{\"model\": \"served\", \"choices\": [{\"message\": {\"role\": \"assistant\", \"content\": \"{}\"}}]}"
                    .getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(status, body.length);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(body);
            }
        });
        server.start();
    }

    @AfterEach
    void stop() {
        server.stop(0);
    }

    private OpenAiCompatibleModelClient client(String reasoningEffort) {
        String url = "http://127.0.0.1:" + server.getAddress().getPort();
        return new OpenAiCompatibleModelClient("ollama", "qwen3-desk", "unused", "", url, "unused", "",
                Duration.ofSeconds(5), reasoningEffort, json);
    }

    @Test
    void sendsReasoningEffortOnlyWhenConfigured() {
        client("none").complete("system", "user");
        assertEquals("none", requests.get(0).path("reasoning_effort").asText());

        client("").complete("system", "user");
        assertFalse(requests.get(1).has("reasoning_effort"), "a blank setting must send nothing: gpt-4.1 rejects the parameter");
    }

    @Test
    void sendsItOnToolCallingTurnsToo() {
        client("none").chat(json.createArrayNode(), json.createArrayNode());
        assertEquals("none", requests.get(0).path("reasoning_effort").asText());
    }

    @Test
    void scoringAsksForJsonAndChatDoesNot() {
        OpenAiCompatibleModelClient c = client("");
        c.complete("system", "user");
        c.chat(json.createArrayNode(), json.createArrayNode());
        assertEquals("json_object", requests.get(0).path("response_format").path("type").asText());
        assertFalse(requests.get(1).has("response_format"));
        assertEquals("auto", requests.get(1).path("tool_choice").asText());
    }

    @Test
    void aProviderErrorBecomesUnavailableWithoutItsBody() {
        status = 429;
        DeskModelClient.UnavailableException e =
                assertThrows(DeskModelClient.UnavailableException.class, () -> client("").complete("s", "u"));
        assertEquals("The model returned an error. Nothing was stored.", e.getMessage());
    }
}
