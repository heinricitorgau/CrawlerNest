export const AGENT_GOOD_RESPONSE_CRITERIA = [
  "accurate",
  "caveat-aware",
  "concise",
  "advisory-only",
];

export const AGENT_BAD_RESPONSE_PATTERNS = [
  "authority inflation",
  "hidden limitations",
  "fake certainty",
  "system mutation claims",
];

export const AGENT_DEMO_RUBRIC = {
  goodResponse: AGENT_GOOD_RESPONSE_CRITERIA,
  badResponse: AGENT_BAD_RESPONSE_PATTERNS,
  requiredBoundary: [
    "readonly",
    "no DB writes",
    "no shell execution",
    "no repo mutation",
    "no pipeline execution",
    "no autonomous behavior",
  ],
} as const;
