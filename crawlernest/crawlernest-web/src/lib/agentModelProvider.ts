import { AGENT_SYSTEM_PROMPT } from "@/lib/agentSystemPrompt";

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
  const baseUrl = status.baseUrl ?? "https://api.openai.com/v1";
  const endpoint = `${baseUrl.replace(/\/$/, "")}/chat/completions`;
  const payload = {
    model: status.modelName,
    temperature: 0.2,
    messages: [
      { role: "system", content: AGENT_SYSTEM_PROMPT },
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
  const text = normalizeAgentResponse(extractOpenAiText(json));
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
