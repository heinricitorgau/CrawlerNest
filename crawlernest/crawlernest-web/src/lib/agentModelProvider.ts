import { AGENT_SYSTEM_PROMPT } from "@/lib/agentSystemPrompt";

export type AgentModelProvider = "mock" | "ollama" | "openai" | "ds4";

export type AgentProviderStatus = {
  configured: boolean;
  providerLabel: string;
  modelName: string | null;
  baseUrl: string | null;
  reason: string | null;
};

export type AgentChatResult = {
  ok: boolean;
  text: string;
  providerLabel: string;
  modelName: string | null;
  baseUrl: string | null;
  warnings: string[];
};

type ProviderEnv = NodeJS.ProcessEnv;
type FetchLike = typeof fetch;

export const MAX_AGENT_MESSAGE_LENGTH = 4000;
const DEFAULT_TIMEOUT_MS = 15000;

/**
 * ds4 runs DeepSeek V4 Flash locally, so a cold prefill or a long answer takes
 * far longer than a hosted API call. 15s would make the provider fall back on
 * almost every real request. 60s matches WEB_AGENT_DS4_TIMEOUT on the Python
 * side, so both clients wait the same amount for the same server.
 *
 * This is the cost of the non-streaming path: the whole answer has to arrive
 * inside one timeout, where a streamed response would reset it per chunk.
 */
const DS4_TIMEOUT_MS = 60000;

const DS4_DEFAULT_BASE_URL = "http://localhost:8000/v1";
const DS4_DEFAULT_MODEL = "deepseek-v4-flash";

const SAFE_ERROR =
  "Agent model provider is unavailable. The request stayed readonly and no CrawlerNest data was modified.";

export function validateAgentMessage(message: unknown): string | null {
  if (typeof message !== "string") {
    return "Message must be a string.";
  }
  const trimmed = message.trim();
  if (!trimmed) {
    return "Message is required.";
  }
  if (trimmed.length > MAX_AGENT_MESSAGE_LENGTH) {
    return `Message is too long. Limit is ${MAX_AGENT_MESSAGE_LENGTH} characters.`;
  }
  return null;
}

export function resolveAgentProvider(env: ProviderEnv = process.env): AgentModelProvider | null {
  const raw = (env.AGENT_MODEL_PROVIDER ?? "mock").trim().toLowerCase();
  if (raw === "mock" || raw === "ollama" || raw === "openai" || raw === "ds4") {
    return raw;
  }
  return null;
}

export function getAgentProviderStatus(env: ProviderEnv = process.env): AgentProviderStatus {
  const provider = resolveAgentProvider(env);
  if (!provider) {
    return {
      configured: false,
      providerLabel: "invalid",
      modelName: null,
      baseUrl: null,
      reason: "Invalid provider. Set AGENT_MODEL_PROVIDER to mock, ollama, or openai.",
    };
  }

  if (provider === "mock") {
    return {
      configured: true,
      providerLabel: "mock",
      modelName: env.AGENT_MODEL_NAME?.trim() || "crawlernest-mock",
      baseUrl: null,
      reason: null,
    };
  }

  if (provider === "ollama") {
    const modelName = env.AGENT_MODEL_NAME?.trim() || "";
    const baseUrl =
      env.AGENT_MODEL_BASE_URL?.trim() || env.OLLAMA_BASE_URL?.trim() || "http://localhost:11434";
    return {
      configured: Boolean(modelName),
      providerLabel: "ollama",
      modelName: modelName || null,
      baseUrl,
      reason: modelName ? null : "Model name is required for Ollama provider.",
    };
  }

  if (provider === "ds4") {
    // ds4 needs no credential: it is a local server with no built-in auth, and
    // an API key only appears when someone fronts it with an auth proxy. So
    // unlike openai there is nothing here that can be "missing" -- both the
    // model and the URL have working defaults, and a wrong URL surfaces at call
    // time as an unreachable provider rather than as a config error.
    return {
      configured: true,
      providerLabel: "ds4",
      modelName: resolveDs4Model(env),
      baseUrl: resolveDs4BaseUrl(env),
      reason: null,
    };
  }

  const modelName = env.AGENT_MODEL_NAME?.trim() || "";
  return {
    configured: Boolean(env.OPENAI_API_KEY?.trim() && modelName),
    providerLabel: "openai",
    modelName: modelName || null,
    baseUrl: env.AGENT_MODEL_BASE_URL?.trim() || "https://api.openai.com/v1",
    reason: !env.OPENAI_API_KEY?.trim()
      ? "OpenAI API key is missing. Configure it server-side before using the OpenAI provider."
      : modelName
        ? null
        : "Model name is required for OpenAI provider.",
  };
}

export async function generateAgentChatResponse(
  message: string,
  options: {
    env?: ProviderEnv;
    fetchImpl?: FetchLike;
    timeoutMs?: number;
  } = {}
): Promise<AgentChatResult> {
  const env = options.env ?? process.env;
  const fetchImpl = options.fetchImpl ?? fetch;
  const status = getAgentProviderStatus(env);
  // A caller-supplied timeout still wins; otherwise each provider gets the
  // budget its latency actually needs.
  const timeoutMs = options.timeoutMs ?? resolveTimeoutMs(status.providerLabel, env);

  if (!status.configured) {
    return {
      ok: false,
      text: SAFE_ERROR,
      providerLabel: status.providerLabel,
      modelName: status.modelName,
      baseUrl: status.baseUrl,
      warnings: [status.reason ?? "Agent provider is not configured."],
    };
  }

  if (status.providerLabel === "mock") {
    return {
      ok: true,
      text: normalizeAgentResponse(buildMockResponse(message)),
      providerLabel: "mock",
      modelName: status.modelName,
      baseUrl: null,
      warnings: ["Mock provider used. No external model was contacted."],
    };
  }

  try {
    if (status.providerLabel === "ollama") {
      return await callOllamaProvider(message, status, fetchImpl, timeoutMs);
    }
    if (status.providerLabel === "openai") {
      return await callOpenAiProvider(message, status, env, fetchImpl, timeoutMs);
    }
    if (status.providerLabel === "ds4") {
      return await callDs4Provider(message, status, env, fetchImpl, timeoutMs);
    }
  } catch {
    return {
      ok: false,
      text: SAFE_ERROR,
      providerLabel: status.providerLabel,
      modelName: status.modelName,
      baseUrl: status.baseUrl,
      warnings: ["Model unavailable or timeout. Raw provider errors are not exposed."],
    };
  }

  return {
    ok: false,
    text: SAFE_ERROR,
    providerLabel: status.providerLabel,
    modelName: status.modelName,
    baseUrl: status.baseUrl,
    warnings: ["Unsupported provider configuration."],
  };
}

function buildMockResponse(message: string): string {
  const intent = message.trim().replace(/\s+/g, " ").slice(0, 240);
  return [
    `I read your request as: "${intent}".`,
    "I can explain CrawlerNest concepts, point you to relevant pages, summarize caveats, and suggest debugging direction.",
    "This response is advisory only. I do not run tools, modify code, write the database, rerun pipelines, or change recommendations.",
    "Useful pages to inspect next: /analytics, /rankings, /recommendations, and /system-status.",
    "Check freshness and source coverage caveats before treating the result as complete.",
  ].join("\n\n");
}

export function normalizeAgentResponse(text: string): string {
  let normalized = text;
  const replacements: Array<[RegExp, string]> = [
    [/\bI(?:'ve| have)? changed the code\b/gi, "I can suggest how to change the code"],
    [/\bI(?:'ve| have)? modified the code\b/gi, "I can suggest how to modify the code"],
    [/\bI(?:'ve| have)? edited the repository\b/gi, "I can suggest what a maintainer could edit"],
    [/\bI(?:'ve| have)? updated the repo(?:sitory)?\b/gi, "I can suggest what a maintainer could update"],
    [/\bI(?:'ve| have)? ran the pipeline\b/gi, "You can run the pipeline"],
    [/\bI(?:'ve| have)? reran the pipeline\b/gi, "You can rerun the pipeline"],
    [/\bI(?:'ve| have)? run the pipeline\b/gi, "You can run the pipeline"],
    [/\bI(?:'ve| have)? updated the database\b/gi, "I can explain how a maintainer can update the database"],
    [/\bI(?:'ve| have)? wrote to the database\b/gi, "I can explain how a maintainer can write to the database"],
    [/\bI(?:'ve| have)? changed recommendations\b/gi, "I can explain recommendation behavior"],
    [/\bI(?:'ve| have)? changed the rankings\b/gi, "I can explain ranking behavior"],
  ];

  for (const [pattern, replacement] of replacements) {
    normalized = normalized.replace(pattern, replacement);
  }

  return normalized;
}

async function callOllamaProvider(
  message: string,
  status: AgentProviderStatus,
  fetchImpl: FetchLike,
  timeoutMs: number
): Promise<AgentChatResult> {
  const baseUrl = status.baseUrl ?? "http://localhost:11434";
  const endpoint = `${baseUrl.replace(/\/$/, "")}/api/chat`;
  const payload = {
    model: status.modelName,
    stream: false,
    messages: [
      { role: "system", content: AGENT_SYSTEM_PROMPT },
      { role: "user", content: message },
    ],
  };
  const json = await postJsonWithTimeout(endpoint, payload, {}, fetchImpl, timeoutMs);
  const text = normalizeAgentResponse(extractOllamaText(json));
  return {
    ok: true,
    text,
    providerLabel: "ollama",
    modelName: status.modelName,
    baseUrl,
    warnings: [],
  };
}

async function callOpenAiProvider(
  message: string,
  status: AgentProviderStatus,
  env: ProviderEnv,
  fetchImpl: FetchLike,
  timeoutMs: number
): Promise<AgentChatResult> {
  return callOpenAiCompatibleProvider(message, {
    providerLabel: "openai",
    baseUrl: status.baseUrl ?? "https://api.openai.com/v1",
    modelName: status.modelName,
    headers: { Authorization: `Bearer ${env.OPENAI_API_KEY ?? ""}` },
    fetchImpl,
    timeoutMs,
  });
}

/**
 * Calls a local ds4 server through its OpenAI-compatible /v1 API.
 *
 * Non-streaming on purpose: `stream: false` is stated rather than left to the
 * default, because ds4 can stream and the choice not to is the thing worth
 * being explicit about.
 */
async function callDs4Provider(
  message: string,
  status: AgentProviderStatus,
  env: ProviderEnv,
  fetchImpl: FetchLike,
  timeoutMs: number
): Promise<AgentChatResult> {
  const apiKey = resolveDs4ApiKey(env);
  return callOpenAiCompatibleProvider(message, {
    providerLabel: "ds4",
    baseUrl: status.baseUrl ?? DS4_DEFAULT_BASE_URL,
    modelName: status.modelName,
    // Only sent when ds4 sits behind an auth-terminating proxy. A bare
    // ds4-server has no authentication, and sending an empty bearer token to
    // one that does would be indistinguishable from sending none.
    headers: apiKey ? { Authorization: `Bearer ${apiKey}` } : {},
    stream: false,
    fetchImpl,
    timeoutMs,
  });
}

/**
 * Shared request path for every OpenAI-compatible provider.
 *
 * openai and ds4 differ only in where they point, whether they carry a
 * credential, and how long they are given; the request encoding and the
 * response parsing are identical, so they are written once.
 */
async function callOpenAiCompatibleProvider(
  message: string,
  options: {
    providerLabel: string;
    baseUrl: string;
    modelName: string | null;
    headers: Record<string, string>;
    stream?: boolean;
    fetchImpl: FetchLike;
    timeoutMs: number;
  }
): Promise<AgentChatResult> {
  const baseUrl = options.baseUrl;
  const endpoint = `${baseUrl.replace(/\/$/, "")}/chat/completions`;
  const payload: Record<string, unknown> = {
    model: options.modelName,
    temperature: 0.2,
    messages: [
      { role: "system", content: AGENT_SYSTEM_PROMPT },
      { role: "user", content: message },
    ],
  };
  if (options.stream !== undefined) {
    payload.stream = options.stream;
  }
  const json = await postJsonWithTimeout(
    endpoint,
    payload,
    options.headers,
    options.fetchImpl,
    options.timeoutMs
  );
  const text = normalizeAgentResponse(extractOpenAiText(json));
  return {
    ok: true,
    text,
    providerLabel: options.providerLabel,
    modelName: options.modelName,
    baseUrl,
    warnings: [],
  };
}

/**
 * Resolves the ds4 endpoint, appending the `/v1` suffix when it is absent.
 *
 * The Python integration documents the trailing `/v1` as optional, so a URL
 * copied from `WEB_AGENT_DS4_BASE_URL` has to work here whichever way it was
 * written; without this, `http://host:8000` would produce a request to
 * `/chat/completions` and 404.
 */
export function resolveDs4BaseUrl(env: ProviderEnv = process.env): string {
  const raw =
    env.AGENT_MODEL_BASE_URL?.trim() ||
    env.WEB_AGENT_DS4_BASE_URL?.trim() ||
    DS4_DEFAULT_BASE_URL;
  const trimmed = raw.replace(/\/+$/, "");
  return trimmed.endsWith("/v1") ? trimmed : `${trimmed}/v1`;
}

function resolveDs4Model(env: ProviderEnv): string {
  return (
    env.AGENT_MODEL_NAME?.trim() ||
    env.WEB_AGENT_DS4_MODEL?.trim() ||
    DS4_DEFAULT_MODEL
  );
}

function resolveDs4ApiKey(env: ProviderEnv): string {
  return env.AGENT_MODEL_API_KEY?.trim() || env.WEB_AGENT_DS4_API_KEY?.trim() || "";
}

/**
 * Per-provider request budget.
 *
 * WEB_AGENT_DS4_TIMEOUT is read in seconds so one environment variable
 * configures the Python client and this one identically.
 */
function resolveTimeoutMs(providerLabel: string, env: ProviderEnv): number {
  if (providerLabel !== "ds4") {
    return DEFAULT_TIMEOUT_MS;
  }
  const configured = Number(env.WEB_AGENT_DS4_TIMEOUT?.trim());
  if (Number.isFinite(configured) && configured > 0) {
    return Math.round(configured * 1000);
  }
  return DS4_TIMEOUT_MS;
}

async function postJsonWithTimeout(
  endpoint: string,
  payload: unknown,
  headers: Record<string, string>,
  fetchImpl: FetchLike,
  timeoutMs: number
): Promise<unknown> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(endpoint, {
      method: "POST",
      cache: "no-store",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...headers,
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error("provider request failed");
    }
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

function extractOllamaText(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    throw new Error("invalid ollama response");
  }
  const record = payload as Record<string, unknown>;
  const message = record.message;
  if (message && typeof message === "object") {
    const content = (message as Record<string, unknown>).content;
    if (typeof content === "string" && content.trim()) {
      return content.trim();
    }
  }
  const response = record.response;
  if (typeof response === "string" && response.trim()) {
    return response.trim();
  }
  throw new Error("ollama returned no text");
}

function extractOpenAiText(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    throw new Error("invalid openai response");
  }
  const choices = (payload as Record<string, unknown>).choices;
  if (!Array.isArray(choices) || choices.length === 0) {
    throw new Error("openai returned no choices");
  }
  const first = choices[0];
  if (!first || typeof first !== "object") {
    throw new Error("openai choice is invalid");
  }
  const message = (first as Record<string, unknown>).message;
  if (!message || typeof message !== "object") {
    throw new Error("openai message is invalid");
  }
  const content = (message as Record<string, unknown>).content;
  if (typeof content === "string" && content.trim()) {
    return content.trim();
  }
  throw new Error("openai returned no text");
}
