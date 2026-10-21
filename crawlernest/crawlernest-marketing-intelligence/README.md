# @crawlernest/marketing-intelligence

`MarketingIntelligenceEngine`: routes a marketing question to a NotFair or Claude Ads
skill, parses what the skill returns into `pass` / `fail` / `unknown` / `not_applicable`
findings with evidence and prioritised action items, and keeps every third-party
platform read-only.

```ts
import { MarketingIntelligenceEngine, defaultSkillRoots, guardPlatformClient } from '@crawlernest/marketing-intelligence';

const engine = new MarketingIntelligenceEngine({
  skillRoots: defaultSkillRoots(repoRoot),          // notfair-plugin/skills, claude-ads/skills
  runner: myRunner,                                  // runs one skill; see SkillRunner
});

engine.route('分析競爭對手的 SEO 與 GA4 流量變化');   // → /seo-analysis, /google-analytics (read_only)
engine.route('審計 Google Ads 廣告帳戶表現');          // → /ads audit google (read_only)
const { reports } = await engine.analyze('審計 Google Ads 廣告帳戶表現');
```

| Module | Does |
| --- | --- |
| `src/catalog.ts` | The skills the router may pick and the phrases (English and Chinese) that pick them. Edit here to add a skill. |
| `src/intentRouter.ts` | Deterministic keyword routing. One task per skill, in the order the user mentioned them; `matchedKeywords` says why. |
| `src/skillRegistry.ts` | Loads `SKILL.md`; refuses one that is missing or whose frontmatter `name` does not match. |
| `src/outputParser.ts` | JSON (Claude Ads `AuditWorkerResult`, a `findings` array, a fenced ```json block) or a text checklist → `IntelligenceReport`. |
| `src/safety.ts` | `guardPlatformClient`, `createDraft`, `executionPolicy`. |
| `src/engine.ts` | `route` → `plan` → `analyze`. |

## Running skills with Claude (`/claude`)

`ClaudeSkillRunner` is a `SkillRunner` that runs one skill as a Claude tool-use loop (`claude-opus-5-5`,
adaptive thinking, effort `high`, streamed, prompt-cached, `fallbacks: "default"` on a refusal).

```ts
import { ClaudeSkillRunner, type ReadTool } from '@crawlernest/marketing-intelligence/claude';

const searchGoogleAds: ReadTool = {
  name: 'search_google_ads',                       // must start with a read verb
  description: 'Run a GAQL query against the connected Google Ads account.',
  platform: 'google_ads',
  inputSchema: { type: 'object', properties: { query: { type: 'string' } }, required: ['query'] },
  run: async ({ query }) => guardedAds.search(String(query)),   // a client from guardPlatformClient
};

const engine = new MarketingIntelligenceEngine({
  skillRoots: defaultSkillRoots(repoRoot),
  runner: new ClaudeSkillRunner({ tools: [searchGoogleAds] }),   // new Anthropic() credentials
});
```

- The agent gets the host's read tools whose `platform` is in the task's scope, `read_skill_file` (files the
  SKILL.md points to, inside the skill library only), and `submit_findings`, whose input is the run's result.
  `proposed_changes` exists in that schema only for `draft_only` tasks.
- A tool not named as a read is refused when the runner is built. A `MutationBlockedError` from a tool aborts
  the run; the engine reports it as `failed` with the violation recorded.
- Tool results are wrapped as untrusted `<tool_result_data>`; a result over `maxResultChars` is cut with a note
  telling Claude it was cut.
- Skill steps that need something the run does not have (a script, an export, an unconnected platform) end as
  `unknown` findings and `missing_inputs`, never as guesses.

## Safe by design

- `AccessMode` is `read_only | draft_only`. There is no write mode to switch on.
- A change request routes to `/ads optimize --draft`. `--apply` is removed from the input and noted.
- `guardPlatformClient` lets only read-named methods (`get*`, `list*`, `search*`, `runReport`, …) through
  and throws `MutationBlockedError` for anything else, including methods on objects a read returned.
- `ChangeDraft` is frozen and `applied` is the literal `false`. Skill output that claims a change was
  applied is recorded in `policyViolations`.

## The honesty rules in the parser

- A `pass` or `fail` with no evidence is reported as `unknown`, with `downgradedFrom` set.
- A status the parser does not recognise is `unknown`, never `pass`.
- `caveats` is never empty; the report status is `provisional` while any check is `unknown`.

```bash
npm install && npm test
```
