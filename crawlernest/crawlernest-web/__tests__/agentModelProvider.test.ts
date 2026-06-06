import {
  generateAgentChatResponse,
  getAgentProviderStatus,
  MAX_AGENT_MESSAGE_LENGTH,
  normalizeAgentResponse,
  validateAgentMessage,
} from "@/lib/agentModelProvider";
import { AGENT_SYSTEM_PROMPT } from "@/lib/agentSystemPrompt";

describe("agent model provider bridge", () => {
  it("defines readonly boundaries in the shared system prompt", () => {
    expect(AGENT_SYSTEM_PROMPT).toContain("explainable university intelligence platform");
    expect(AGENT_SYSTEM_PROMPT).toContain("readonly");
    expect(AGENT_SYSTEM_PROMPT).toContain("advisory-only");
    expect(AGENT_SYSTEM_PROMPT).toContain("must not claim");
    expect(AGENT_SYSTEM_PROMPT).toContain("wrote the database");
    expect(AGENT_SYSTEM_PROMPT).toContain("reran pipelines");
  });

  it("uses the mock provider without environment variables", async () => {
    const result = await generateAgentChatResponse("Explain Oxford", {
      env: {},
      fetchImpl: jest.fn() as unknown as typeof fetch,
    });

    expect(result.ok).toBe(true);
    expect(result.providerLabel).toBe("mock");
    expect(result.text).toContain("Explain Oxford");
    expect(result.text).toContain("advisory only");
    expect(result.text).toContain("I do not run tools");
    expect(result.text).toContain("/analytics");
  });

  it("returns a safe error when OpenAI key is missing", async () => {
    const result = await generateAgentChatResponse("hello", {
      env: {
        AGENT_MODEL_PROVIDER: "openai",
        AGENT_MODEL_NAME: "example-model",
      },
      fetchImpl: jest.fn() as unknown as typeof fetch,
    });

    expect(result.ok).toBe(false);
    expect(result.providerLabel).toBe("openai");
    expect(result.text).toContain("provider is unavailable");
    expect(result.text).not.toContain("OPENAI_API_KEY");
    expect(result.warnings[0]).toContain("OpenAI API key is missing");
  });

  it("returns a safe status for invalid providers", () => {
    const status = getAgentProviderStatus({ AGENT_MODEL_PROVIDER: "surprise" });

    expect(status.configured).toBe(false);
    expect(status.providerLabel).toBe("invalid");
    expect(status.reason).toContain("Invalid provider");
  });

  it("normalizes unsafe provider claims into advisory wording", () => {
    const normalized = normalizeAgentResponse(
      "I changed the code. I ran the pipeline. I updated the database."
    );

    expect(normalized).toContain("I can suggest how to change the code");
    expect(normalized).toContain("You can run the pipeline");
    expect(normalized).toContain("I can explain how a maintainer can update the database");
    expect(normalized).not.toContain("I changed the code");
    expect(normalized).not.toContain("I ran the pipeline");
    expect(normalized).not.toContain("I updated the database");
  });

  it("uses the shared system prompt for OpenAI requests and normalizes output", async () => {
    const fetchMock = jest.fn(async () => ({
      ok: true,
      json: async () => ({
        choices: [
          {
            message: {
              content: "I changed the code and I ran the pipeline.",
            },
          },
        ],
      }),
    })) as unknown as jest.MockedFunction<typeof fetch>;

    const result = await generateAgentChatResponse("How do I debug stale data?", {
      env: {
        AGENT_MODEL_PROVIDER: "openai",
        AGENT_MODEL_NAME: "example-model",
        OPENAI_API_KEY: "test-key",
      },
      fetchImpl: fetchMock,
    });

    const requestBody = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(requestBody.messages[0]).toEqual({
      role: "system",
      content: AGENT_SYSTEM_PROMPT,
    });
    expect(result.ok).toBe(true);
    expect(result.text).toContain("I can suggest how to change the code");
    expect(result.text).toContain("You can run the pipeline");
  });

  it("rejects long input before provider execution", () => {
    const message = "x".repeat(MAX_AGENT_MESSAGE_LENGTH + 1);

    expect(validateAgentMessage(message)).toContain("too long");
  });

  it("handles provider timeout with a safe error", async () => {
    const slowFetch = jest.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new Error("aborted")));
        })
    ) as unknown as typeof fetch;

    const result = await generateAgentChatResponse("hello", {
      env: {
        AGENT_MODEL_PROVIDER: "ollama",
        AGENT_MODEL_NAME: "llama3.1",
        OLLAMA_BASE_URL: "http://localhost:11434",
      },
      fetchImpl: slowFetch,
      timeoutMs: 1,
    });

    expect(result.ok).toBe(false);
    expect(result.providerLabel).toBe("ollama");
    expect(result.text).toContain("provider is unavailable");
    expect(result.warnings[0]).toContain("Model unavailable or timeout");
  });
});
