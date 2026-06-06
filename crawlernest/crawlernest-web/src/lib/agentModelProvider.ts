export type AgentModelProvider = "mock" | "ollama" | "openai";

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

const SAFE_ERROR =
  "Agent model provider is unavailable. The request stayed readonly and no CrawlerNest data was modified.";

const SYSTEM_PROMPT = [
  "You are CrawlerNest Agent in readonly advisory mode.",
  "You may explain CrawlerNest concepts, suggest pages to inspect, and summarize next human steps.",
  "You must not claim to run shell commands, edit files, run pipelines, write databases, or change rankings.",
  "Keep answers concise, operationally honest, and demo-safe.",
].join(" ");

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
  if (raw === "mock" || raw === "ollama" || raw === "openai") {
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
      reason: "Unsupported AGENT_MODEL_PROVIDER. Use mock, ollama, or openai.",
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
      reason: modelName ? null : "AGENT_MODEL_NAME is required for Ollama.",
    };
  }

  const modelName = env.AGENT_MODEL_NAME?.trim() || "";
  return {
    configured: Boolean(env.OPENAI_API_KEY?.trim() && modelName),
    providerLabel: "openai",
    modelName: modelName || null,
    baseUrl: env.AGENT_MODEL_BASE_URL?.trim() || "https://api.openai.com/v1",
    reason: !env.OPENAI_API_KEY?.trim()
      ? "OPENAI_API_KEY is required for OpenAI provider."
      : modelName
        ? null
        : "AGENT_MODEL_NAME is required for OpenAI provider.",
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
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const status = getAgentProviderStatus(env);

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
      text: buildMockResponse(message),
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
  } catch {
    return {
      ok: false,
      text: SAFE_ERROR,
      providerLabel: status.providerLabel,
      modelName: status.modelName,
      baseUrl: status.baseUrl,
      warnings: ["Provider request failed or timed out. Raw provider errors are not exposed."],
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
    "This Phase 1 agent response is advisory only. It does not run tools, edit the repository, write the database, or rerun CrawlerNest pipelines.",
    "Useful CrawlerNest pages to inspect next: /analytics, /rankings, /recommendations, and /system-status.",
  ].join("\n\n");
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
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: message },
    ],
  };
  const json = await postJsonWithTimeout(endpoint, payload, {}, fetchImpl, timeoutMs);
  const text = extractOllamaText(json);
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
  const baseUrl = status.baseUrl ?? "https://api.openai.com/v1";
  const endpoint = `${baseUrl.replace(/\/$/, "")}/chat/completions`;
  const payload = {
    model: status.modelName,
    temperature: 0.2,
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: message },
    ],
  };
  const json = await postJsonWithTimeout(
    endpoint,
    payload,
    { Authorization: `Bearer ${env.OPENAI_API_KEY ?? ""}` },
    fetchImpl,
    timeoutMs
  );
  const text = extractOpenAiText(json);
  return {
    ok: true,
    text,
    providerLabel: "openai",
    modelName: status.modelName,
    baseUrl,
    warnings: [],
  };
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
