import {
  generateAgentChatResponse,
  getAgentProviderStatus,
  MAX_AGENT_MESSAGE_LENGTH,
  normalizeAgentResponse,
  resolveDs4BaseUrl,
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

describe("ds4 provider", () => {
  const BASE_ENV = {
    NODE_ENV: "test",
    AGENT_MODEL_PROVIDER: "ds4",
  } as unknown as NodeJS.ProcessEnv;

  function okFetch(content: string) {
    return jest.fn(async () => ({
      ok: true,
      json: async () => ({ choices: [{ message: { content } }] }),
    })) as unknown as jest.MockedFunction<typeof fetch>;
  }

  it("is configured without any credential", () => {
    const status = getAgentProviderStatus(BASE_ENV);

    // Unlike openai, a bare ds4 server has nothing to authenticate against, so
    // there is no key whose absence should disable the provider.
    expect(status.configured).toBe(true);
    expect(status.providerLabel).toBe("ds4");
    expect(status.reason).toBeNull();
    expect(status.modelName).toBe("deepseek-v4-flash");
    expect(status.baseUrl).toBe("http://localhost:8000/v1");
  });

  it("reads model and base url from the shared WEB_AGENT_DS4_ variables", () => {
    const status = getAgentProviderStatus({
      ...BASE_ENV,
      WEB_AGENT_DS4_BASE_URL: "http://10.0.0.42:8000/v1",
      WEB_AGENT_DS4_MODEL: "deepseek-v4-flash-q4",
    } as unknown as NodeJS.ProcessEnv);

    expect(status.baseUrl).toBe("http://10.0.0.42:8000/v1");
    expect(status.modelName).toBe("deepseek-v4-flash-q4");
  });

  it("lets AGENT_MODEL_ variables override the shared ones", () => {
    const status = getAgentProviderStatus({
      ...BASE_ENV,
      AGENT_MODEL_BASE_URL: "http://primary:8000/v1",
      WEB_AGENT_DS4_BASE_URL: "http://secondary:8000/v1",
      AGENT_MODEL_NAME: "primary-model",
      WEB_AGENT_DS4_MODEL: "secondary-model",
    } as unknown as NodeJS.ProcessEnv);

    expect(status.baseUrl).toBe("http://primary:8000/v1");
    expect(status.modelName).toBe("primary-model");
  });

  describe("base url normalization", () => {
    const env = (base: string) =>
      ({ NODE_ENV: "test", WEB_AGENT_DS4_BASE_URL: base } as unknown as NodeJS.ProcessEnv);

    it("appends the version segment when it is missing", () => {
      // The Python integration documents the suffix as optional, so a URL
      // copied from there has to work whichever way it was written.
      expect(resolveDs4BaseUrl(env("http://host:8000"))).toBe("http://host:8000/v1");
    });

    it("keeps the version segment when it is already there", () => {
      expect(resolveDs4BaseUrl(env("http://host:8000/v1"))).toBe("http://host:8000/v1");
    });

    it("tolerates a trailing slash in either form", () => {
      expect(resolveDs4BaseUrl(env("http://host:8000/"))).toBe("http://host:8000/v1");
      expect(resolveDs4BaseUrl(env("http://host:8000/v1/"))).toBe("http://host:8000/v1");
    });
  });

  it("posts to the OpenAI-compatible chat endpoint with the shared system prompt", async () => {
    const fetchMock = okFetch("Here is what the rankings show.");

    await generateAgentChatResponse("Explain the QS coverage", {
      env: BASE_ENV,
      fetchImpl: fetchMock,
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/v1/chat/completions");
    const body = JSON.parse(String(init?.body));
    expect(body.model).toBe("deepseek-v4-flash");
    expect(body.messages[0]).toEqual({ role: "system", content: AGENT_SYSTEM_PROMPT });
    expect(body.messages[1]).toEqual({ role: "user", content: "Explain the QS coverage" });
  });

  it("asks for a single response rather than a stream", async () => {
    const fetchMock = okFetch("A complete answer.");

    await generateAgentChatResponse("hello", { env: BASE_ENV, fetchImpl: fetchMock });

    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body.stream).toBe(false);
  });

  it("sends no Authorization header when no key is configured", async () => {
    const fetchMock = okFetch("A complete answer.");

    await generateAgentChatResponse("hello", { env: BASE_ENV, fetchImpl: fetchMock });

    const headers = fetchMock.mock.calls[0][1]?.headers as Record<string, string>;
    // Against a proxy that does check, an empty bearer token is
    // indistinguishable from a real one that failed.
    expect(headers.Authorization).toBeUndefined();
  });

  it("sends a bearer token when ds4 sits behind an auth proxy", async () => {
    const fetchMock = okFetch("A complete answer.");

    await generateAgentChatResponse("hello", {
      env: { ...BASE_ENV, WEB_AGENT_DS4_API_KEY: "proxy-token" } as unknown as NodeJS.ProcessEnv,
      fetchImpl: fetchMock,
    });

    const headers = fetchMock.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer proxy-token");
  });

  it("normalizes claims the model makes about having changed things", async () => {
    const fetchMock = okFetch("I updated the database and I ran the pipeline.");

    const result = await generateAgentChatResponse("do it", {
      env: BASE_ENV,
      fetchImpl: fetchMock,
    });

    expect(result.ok).toBe(true);
    expect(result.providerLabel).toBe("ds4");
    expect(result.text).toContain("I can explain how a maintainer can update the database");
    expect(result.text).toContain("You can run the pipeline");
    expect(result.text).not.toContain("I updated the database");
  });

  it("falls back to the safe error when the server is unreachable", async () => {
    const failingFetch = jest.fn(async () => {
      throw new Error("ECONNREFUSED");
    }) as unknown as typeof fetch;

    const result = await generateAgentChatResponse("hello", {
      env: BASE_ENV,
      fetchImpl: failingFetch,
    });

    expect(result.ok).toBe(false);
    expect(result.providerLabel).toBe("ds4");
    expect(result.text).toContain("provider is unavailable");
    // The raw connection error must not reach the browser.
    expect(result.text).not.toContain("ECONNREFUSED");
    expect(result.warnings[0]).toContain("Model unavailable or timeout");
  });

  it("times out rather than hanging when the model never answers", async () => {
    const slowFetch = jest.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new Error("aborted")));
        })
    ) as unknown as typeof fetch;

    const result = await generateAgentChatResponse("hello", {
      env: BASE_ENV,
      fetchImpl: slowFetch,
      timeoutMs: 1,
    });

    expect(result.ok).toBe(false);
    expect(result.providerLabel).toBe("ds4");
    expect(result.warnings[0]).toContain("Model unavailable or timeout");
  });

  it("gives a local model far longer than the hosted default before aborting", async () => {
    // A hosted API answers in a couple of seconds; DeepSeek V4 Flash on local
    // hardware takes tens. Reusing the 15s hosted default would make ds4 fall
    // back on almost every real request, so the abort must not fire at 15s.
    let abortedAfterMs: number | null = null;
    const startedAt = Date.now();
    const neverAnswers = jest.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            abortedAfterMs = Date.now() - startedAt;
            reject(new Error("aborted"));
          });
        })
    ) as unknown as typeof fetch;

    jest.useFakeTimers({ doNotFake: ["Date"] });
    const pending = generateAgentChatResponse("hello", {
      env: BASE_ENV,
      fetchImpl: neverAnswers,
    });

    jest.advanceTimersByTime(15000);
    await Promise.resolve();
    expect(abortedAfterMs).toBeNull();

    jest.advanceTimersByTime(45000);
    const result = await pending;
    jest.useRealTimers();

    expect(abortedAfterMs).not.toBeNull();
    expect(result.ok).toBe(false);
  });

  it("honours WEB_AGENT_DS4_TIMEOUT so one variable configures both clients", async () => {
    let abortedAfterMs: number | null = null;
    const startedAt = Date.now();
    const neverAnswers = jest.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            abortedAfterMs = Date.now() - startedAt;
            reject(new Error("aborted"));
          });
        })
    ) as unknown as typeof fetch;

    jest.useFakeTimers({ doNotFake: ["Date"] });
    const pending = generateAgentChatResponse("hello", {
      // Seconds, matching the Python client's variable of the same name.
      env: { ...BASE_ENV, WEB_AGENT_DS4_TIMEOUT: "5" } as unknown as NodeJS.ProcessEnv,
      fetchImpl: neverAnswers,
    });

    jest.advanceTimersByTime(4000);
    await Promise.resolve();
    expect(abortedAfterMs).toBeNull();

    jest.advanceTimersByTime(2000);
    await pending;
    jest.useRealTimers();

    expect(abortedAfterMs).not.toBeNull();
  });
});
