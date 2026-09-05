/**
 * Which agent warnings are meant for the person reading the page.
 *
 * `TaskResponse.warnings` carries two kinds of string, and they are not for the
 * same audience:
 *
 * - Disclosures about the answer itself, emitted with a machine-readable code
 *   prefix — `UnsupportedYearWarning: Dataset is strictly locked to the 2026
 *   snapshot...`. The reader needs these to interpret what they are looking at.
 * - Operational notes about how the prose was produced — "No web generation
 *   provider configured; deterministic fallback used.", "No ranking rows to
 *   explain; deterministic reply used." These are true and worth keeping, but
 *   they are about the generator, not about the data.
 *
 * The second kind fires on nearly every response when no LLM provider is
 * configured. Putting it in a yellow banner would leave the banner permanently
 * lit, and a banner that is always on is one nobody reads — including on the
 * turn where the year disclosure actually matters. So the banner shows coded
 * disclosures and the debug panel keeps showing everything, which is where the
 * uncoded notes were already being read.
 *
 * The code prefix is the contract, not the wording: the sentence after it is
 * rendered exactly as the backend wrote it. Rewording a disclosure in the
 * frontend is how the four copies of the caveat strings drifted apart (see
 * `caveatMessages.ts`), and this avoids opening a fifth front.
 */

/**
 * Emitted by `crawlernest/agent/web_agent/policy/unsupported_year.py` when a
 * request names a ranking year the warehouse does not hold. Kept as a constant
 * so callers match the code rather than the prose.
 */
export const UNSUPPORTED_YEAR_WARNING_CODE = "UnsupportedYearWarning";

/** `SomeNameWarning: ` at the head of a warning string. */
const WARNING_CODE_PREFIX = /^([A-Za-z][A-Za-z0-9]*Warning):\s*/;

export type AgentWarning = {
  /** The code prefix, or null when the warning carries none. */
  code: string | null;
  /** The disclosure text, verbatim, with the code prefix removed. */
  message: string;
  /** The original string, unmodified. */
  raw: string;
};

export function parseAgentWarning(raw: string): AgentWarning {
  const match = WARNING_CODE_PREFIX.exec(raw);
  if (!match) {
    return { code: null, message: raw, raw };
  }
  return { code: match[1], message: raw.slice(match[0].length), raw };
}

/**
 * The coded disclosures, in the order the backend emitted them.
 *
 * Ignores blank entries and anything that is not a string: this reads a JSON
 * payload, and a malformed one must not blank the response it annotates.
 */
export function selectDisclosureWarnings(warnings: unknown): AgentWarning[] {
  if (!Array.isArray(warnings)) {
    return [];
  }
  return warnings
    .filter((warning): warning is string => typeof warning === "string" && warning.trim() !== "")
    .map(parseAgentWarning)
    .filter((warning) => warning.code !== null);
}

/**
 * A code turned into a badge label — "UnsupportedYearWarning" reads as
 * "Unsupported year". Only the code is reworded; the disclosure is not.
 */
export function humanizeWarningCode(code: string): string {
  const words = code
    .replace(/Warning$/, "")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .trim();
  if (words === "") {
    return "Warning";
  }
  return words.charAt(0).toUpperCase() + words.slice(1).toLowerCase();
}
