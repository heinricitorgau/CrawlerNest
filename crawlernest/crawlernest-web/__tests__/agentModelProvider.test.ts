import {
  generateAgentChatResponse,
  getAgentProviderStatus,
  MAX_AGENT_MESSAGE_LENGTH,
  validateAgentMessage,
} from "@/lib/agentModelProvider";

describe("agent model provider bridge", () => {
  it("uses the mock provider without environment variables", async () => {
    const result = await generateAgentChatResponse("Explain Oxford", {
      env: {},
      fetchImpl: jest.fn() as unknown as typeof fetch,
    });

    expect(result.ok).toBe(true);
    expect(result.providerLabel).toBe("mock");
    expect(result.text).toContain("Explain Oxford");
    expect(result.text).toContain("advisory only");
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
    expect(result.warnings[0]).toContain("OPENAI_API_KEY");
  });

  it("returns a safe status for invalid providers", () => {
    const status = getAgentProviderStatus({ AGENT_MODEL_PROVIDER: "surprise" });

    expect(status.configured).toBe(false);
    expect(status.providerLabel).toBe("invalid");
    expect(status.reason).toContain("Unsupported");
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
    expect(result.warnings[0]).toContain("timed out");
  });
});
