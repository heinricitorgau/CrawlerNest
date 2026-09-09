/**
 * The chat route's first pass: ask the engine, then let the model write.
 *
 * `/api/agent/chat` posts to an LLM and returns prose. The engine — the thing
 * that reads the warehouse, substitutes DATASET_YEAR for a year we do not hold,
 * and attaches the disclosure saying so — was never in that path, so a question
 * like "QS 2025 rankings" came back fluent and undisclosed.
 *
 * This module is pass one. It runs the request through the agent API's task
 * endpoint with generation switched off, and hands the route the rows and the
 * warnings. Pass two is the model call that was already there.
 *
 * Three properties this is built around:
 *
 * - **It never throws and never blocks an answer.** The agent API on 8090 and
 *   the warehouse behind it are not dependencies chat had yesterday. If either
 *   is down the pass returns nothing and the route answers exactly as before.
 *   A disclosure is worth having; it is not worth taking the chat down for.
 * - **Warnings are read even from a failed response.** The engine attaches
 *   request-level disclosures in `_respond`, which every branch passes through
 *   — including the error one. A warehouse outage returns HTTP 500 *and* the
 *   year disclosure, and the second is still true.
 * - **The gate is loose on purpose.** It decides whether to spend a call, not
 *   whether a year is unsupported; Python owns that, and owns the wording. An
 *   over-eager gate costs one cheap call that returns no warnings. A gate that
 *   tried to be clever here would be a second, drifting copy of a rule that
 *   already has one home.
 */

const AGENT_TASK_PATH = "/api/v1/agent/tasks";
const DEFAULT_TIMEOUT_MS = 4000;

/**
 * Signals that the message is asking about warehouse data rather than making
 * conversation.
 *
 * Broad, but not unbounded: every English token is word-bounded, and "THE" as
 * a source name is left out entirely. Python's shared intent list carries
 * `\bthe\b` for Times Higher Education, which is correct there and would fire
 * on nearly every English sentence here — turning a gate into an always-on
 * switch. The point of the gate is that an ordinary "hello" costs nothing.
 */
const QUERY_INTENT =
  /\brank(?:ing|ings|ed)?\b|\buniversit(?:y|ies)\b|\bcollege\b|\bqs\b|\barwu\b|\brecommend\b|\bcompare\b|排名|大學|大学|學校|学校|推薦|推荐|比較|比较/i;

/** Any four-digit year, without the rank-threshold exclusion Python applies. */
const YEAR_MENTION = /(?<![\d.])(?:19|20)\d{2}(?!\d)/;

export type EngineTaskOutcome = {
  /** Whether the engine was consulted at all. */
  consulted: boolean;
  /** Response-level warnings, empty when the pass was skipped or failed. */
  warnings: string[];
  /** The formatter payload, when there was one. */
  data: Record<string, unknown> | null;
  /** Why the pass produced nothing, for the debug panel. Null on success. */
  skippedReason: string | null;
};

const NOT_CONSULTED = (reason: string): EngineTaskOutcome => ({
  consulted: false,
  warnings: [],
  data: null,
  skippedReason: reason,
});

/**
 * Whether this message earns an engine call.
 *
 * A year mention alone is enough: "what about 2025?" carries no query keyword
 * and is exactly the turn that needs the disclosure.
 */
export function shouldConsultEngine(message: string): boolean {
  if (typeof message !== "string" || message.trim() === "") {
    return false;
  }
  return YEAR_MENTION.test(message) || QUERY_INTENT.test(message);
}

function readWarnings(body: unknown): string[] {
  const data = (body as { data?: { warnings?: unknown } } | null)?.data;
  if (!Array.isArray(data?.warnings)) {
    return [];
  }
  return data.warnings.filter(
    (warning): warning is string => typeof warning === "string" && warning.trim() !== ""
  );
}

function readData(body: unknown): Record<string, unknown> | null {
  const inner = (body as { data?: { data?: unknown } } | null)?.data?.data;
  return inner && typeof inner === "object" && !Array.isArray(inner)
    ? (inner as Record<string, unknown>)
    : null;
}

export async function runEngineTask(
  message: string,
  options: {
    context?: Record<string, unknown>;
    baseUrl?: string;
    fetchImpl?: typeof fetch;
    timeoutMs?: number;
  } = {}
): Promise<EngineTaskOutcome> {
  if (!shouldConsultEngine(message)) {
    return NOT_CONSULTED("no data question detected");
  }

  const fetchImpl = options.fetchImpl ?? fetch;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetchImpl(`${options.baseUrl ?? ""}${AGENT_TASK_PATH}`, {
      method: "POST",
      cache: "no-store",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        mode: "web",
        // data_query is the kind a year applies to, and its tool pulls country
        // and entity out of the prompt on its own. The chat surface does not
        // render engine rows yet, so picking a kind per message would be
        // routing nobody reads the result of.
        kind: "data_query",
        user_input: message,
        context: options.context ?? {},
        // Pass two writes the prose; the engine must not spend a model call
        // writing its own. And a phrasing accident must not hand a chat turn
        // to the dev agent, whose replies carry no disclosures.
        constraints: { generation: "disabled", route: "web" },
        source: "web",
      }),
    });

    // Deliberately not gated on response.ok: a warehouse outage answers 500 and
    // still carries the request-level disclosure, which is still true.
    const body = await response.json();
    return {
      consulted: true,
      warnings: readWarnings(body),
      data: readData(body),
      skippedReason: null,
    };
  } catch {
    // Network failure, timeout, or a body that was not JSON. The chat answer
    // does not depend on this pass, so there is nothing to report but the fact.
    return NOT_CONSULTED("agent engine unavailable");
  } finally {
    clearTimeout(timer);
  }
}
