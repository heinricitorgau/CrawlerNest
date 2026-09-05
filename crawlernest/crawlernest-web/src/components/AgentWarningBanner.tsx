"use client";

import {
  humanizeWarningCode,
  selectDisclosureWarnings,
} from "@/lib/agentWarnings";

type AgentWarningBannerProps = {
  /** `response.data.warnings` as the agent API returned it. */
  warnings: unknown;
};

/**
 * The coded disclosures on an agent response, shown above the answer.
 *
 * Above rather than below on purpose: the year disclosure changes how the
 * paragraphs underneath should be read, and a caveat that arrives after the
 * thing it qualifies has already been read is a caveat that arrived late.
 *
 * Renders nothing when there is nothing to disclose, so the ordinary response
 * — the overwhelming majority — is unchanged. Filtering lives in
 * `selectDisclosureWarnings` rather than at the call site so no caller can
 * accidentally spill the generator's operational notes onto a user-facing page.
 */
export default function AgentWarningBanner({ warnings }: AgentWarningBannerProps) {
  const disclosures = selectDisclosureWarnings(warnings);
  if (disclosures.length === 0) {
    return null;
  }

  return (
    <div
      role="alert"
      aria-label="Response disclosures"
      className="mb-4 rounded-2xl border border-[#f0d8b8] bg-[#fffbf4] px-4 py-3"
    >
      <ul className="space-y-2">
        {disclosures.map((warning) => (
          <li
            key={warning.raw}
            data-warning-code={warning.code ?? undefined}
            className="flex items-start gap-2.5"
          >
            <span aria-hidden="true" className="mt-0.5 shrink-0 text-[#c47c1a]">
              ▲
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-[#a4761f]">
                {humanizeWarningCode(warning.code as string)}
              </div>
              <p className="mt-0.5 text-xs leading-5 text-[#7c5c1a]">{warning.message}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
