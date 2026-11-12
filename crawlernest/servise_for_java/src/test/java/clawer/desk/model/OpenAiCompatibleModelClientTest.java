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
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

/**
 * What the client puts on the wire, against a local stand-in for an
 * OpenAI-compatible server. No network, no model.
 */
class OpenAiCompatibleModelClientTest {

    private final ObjectMapper json = new ObjectMapper();
    private final List<JsonNode> requests = new ArrayList<>();
    private HttpServer server;
    private int status = 200;
    private String usage = "";

    @BeforeEach
    void start() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/v1/chat/completions", exchange -> {
            requests.add(json.readTree(exchange.getRequestBody()));
            byte[] body = ("{\"model\": \"served\", " + usage
                    + "\"choices\": [{\"message\": {\"role\": \"assistant\", \"content\": \"{}\"}}]}")
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

    private OpenAiCompatibleModelClient recordingClient(ModelUsageLedger ledger, String baseUrl) {
        return new OpenAiCompatibleModelClient("ollama", "qwen3-desk", "unused", "", baseUrl, "unused", "",
                Duration.ofSeconds(5), "", json, ledger);
    }

    @Test
    void recordsEachCallWithTheProvidersOwnTokenFigures() {
        ModelUsageLedger ledger = mock(ModelUsageLedger.class);
        String url = "http://127.0.0.1:" + server.getAddress().getPort();

        usage = "\"usage\": {\"prompt_tokens\": 812, \"completion_tokens\": 95}, ";
        recordingClient(ledger, url).complete("s", "u");
        verify(ledger).record(null, "(no request)", "served", ModelUsageLedger.Outcome.OK, 812, 95);

        // No usage block: unknown, recorded as null, never as 0.
        usage = "";
        recordingClient(ledger, url).chat(json.createArrayNode(), json.createArrayNode());
        verify(ledger).record(null, "(no request)", "served", ModelUsageLedger.Outcome.OK, null, null);

        status = 500;
        assertThrows(DeskModelClient.UnavailableException.class, () -> recordingClient(ledger, url).complete("s", "u"));
        verify(ledger).record(null, "(no request)", "qwen3-desk", ModelUsageLedger.Outcome.PROVIDER_ERROR, null, null);
    }

    @Test
    void anUnreachableProviderIsRecordedAsSuch() {
        ModelUsageLedger ledger = mock(ModelUsageLedger.class);
        String url = "http://127.0.0.1:" + server.getAddress().getPort();
        server.stop(0);
        assertThrows(DeskModelClient.UnavailableException.class, () -> recordingClient(ledger, url).complete("s", "u"));
        verify(ledger).record(null, "(no request)", "qwen3-desk", ModelUsageLedger.Outcome.UNREACHABLE, null, null);
    }

    @Test
    void anUnconfiguredModelMakesNoCallAndRecordsNothing() {
        ModelUsageLedger ledger = mock(ModelUsageLedger.class);
        OpenAiCompatibleModelClient mockProvider = new OpenAiCompatibleModelClient("mock", "", "unused", "", "", "", "",
                Duration.ofSeconds(5), "", json, ledger);
        assertThrows(DeskModelClient.UnavailableException.class, () -> mockProvider.complete("s", "u"));
        verifyNoInteractions(ledger);
    }

    @Test
    void aProviderErrorBecomesUnavailableWithoutItsBody() {
        status = 429;
        DeskModelClient.UnavailableException e =
                assertThrows(DeskModelClient.UnavailableException.class, () -> client("").complete("s", "u"));
        assertEquals("The model returned an error. Nothing was stored.", e.getMessage());
    }
}
