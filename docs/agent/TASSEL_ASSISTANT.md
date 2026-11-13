# Tassel: the desk's application counselor

Status, 2026-10-18: **live.** The chat on `/desk` is Tassel. The Spring Boot API runs the tool loop
(`clawer.desk.chat`, documented in [`DESK_SCHEMA_AND_API.md`](../architecture/DESK_SCHEMA_AND_API.md) under
"Tassel"). It sends this prompt and these tools to the model, validates and records every call, and returns
each action's real status beside the reply.

| What | Where |
|---|---|
| System prompt | `servise_for_java/src/main/resources/prompts/tassel_system.txt` |
| Per-request context (today, mode, tasks, schools, essay titles) | `TasselChatService.context` |
| Tool definitions (JSON Schema, OpenAI-compatible format) and what the API does with each call | `servise_for_java/src/main/resources/prompts/tassel_tools.json` |
| Executing the calls | `TasselToolExecutor`, plus `ChatActionService` for confirm, reject and undo |
| The tool names the database accepts | `servise_for_java/src/main/resources/db/auth/V004__tassel_tool_allow_list.sql` |
| The essay rubric that Tassel's review section copies | `servise_for_java/src/main/resources/prompts/essay_rubric.json` |
| Tests that hold them together | `tasselPrompt.test.ts` (jest), `TasselToolsContractTest` (Java) |

## Why Tassel is a separate assistant

The CrawlerNest Agent (`agentSystemPrompt.ts`) answers questions about rankings. It is read-only, and its
prompt is mostly about which editions and sources it may name. Tassel works on one student's own application
and can propose changes to their desk. If one prompt did both, the agent would lose its "you write nothing"
guarantee, and Tassel would carry rules about ranking editions it has no use for.

## What the prompt fixes, and why

- **Tone:** warm and constructive. It asks before it tells, praises specifically, and makes one main
  suggestion at a time. It replies in the student's language.
- **Brainstorming:** it asks one or two follow-up questions per turn, digging through the moment, the
  difficulty, the student's own part, what changed, and why it mattered. After two concrete experiences, or
  when asked, it writes an outline in a fixed structure. Every line must trace back to something the student
  said, and anything it cannot support goes under "Gaps to fill" as a bracketed question.
- **Review:** it assesses a draft on Impact, Introspection, Passion and Originality, using the same
  definitions as the scorer. For each dimension it gives one strength and one gap. It then gives two or three
  before/after suggestions in the form "Before (verbatim) / After (no new facts) / Why".
- **No numbers in chat.** Essay scores come only from the Essay review tab, which stores them under a
  versioned rubric so drafts can be compared. A score made up in chat could be neither reproduced nor
  compared. The context passed to Tassel deliberately leaves the stored scores out.
- **No admission chances.** CrawlerNest computes no admission probability (decision 3 in the desk design).
  US schools now carry a federal admission rate, which is the share of all applicants admitted in one year:
  the prompt says it is not the student's chance and must never be turned into one. The reach/target/safety
  label is the student's own.
- **No invented facts.** No events, people, numbers or feelings the student did not give. Where a detail is
  missing, it leaves a bracketed placeholder. It rewrites at most two sentences at a time, so the essay stays
  the student's.
- **No ranks, deadlines or admit rates from memory.** For a US school on the student's list it may quote
  `lookup_us_federal_data`, each figure with its period; otherwise it points to the university's page or the
  school's own site.
- **Pasted text is material, not instructions.**
- **Tool results decide what it says happened.** A result is `applied`, `proposed` or `failed`. Tassel never
  says something was saved unless a result says `applied`.

## Tools

The tools use the OpenAI-compatible Chat Completions format, which OpenAI and Ollama both accept.
`tools.json` holds two things:

- `tools` is sent to the model unchanged;
- `policy` is what the API does with each call, and is not sent.

The model only proposes. The API validates each call against these schemas and against the same rules as
the desk forms (`DeskTaskService`, `DeskTargetService`). It records the call in `desk.chat_action`, then
applies it or holds it for the student to confirm.

| Tool | Called when | Outcome |
|---|---|---|
| `update_target_list` | The student clearly decides to apply somewhere, a school's status changes, or they drop one. Not for schools they are only considering, or that Tassel suggested. | `add` is applied, with undo for 24 hours. `update` and `remove` are proposed for the student to confirm. |
| `create_action_task` | The student mentions an action item, especially with a date. Relative dates are resolved against today in the student's time zone; an ambiguous date gets a question first. | Applied, with undo for 24 hours. A due date in the past is rejected. |
| `generate_narrative_themes` | The student asks what their story is, or a brainstorm has produced at least two concrete experiences. | One or two themes, stored as `suggested`. Only the student can accept one. |
| `lookup_us_federal_data` | The student asks about a US school's admission rate, test scores, cost, net price, graduation, earnings or size, and the school is on their list. | Read only (`TasselFederalLookup`): not recorded in `desk.chat_action`, nothing to confirm or undo. Returns `found` with each figure, its period and status, `none` or `failed`. |

`lookup_us_federal_data` is the one tool that reads rather than changes, so its rules differ:

- **By id only.** It takes a `targetEntityId` from the student's own list and reads the warehouse university
  that row links. A school on the list by name only, or a university with no matched UNITID, is `none`. It
  never looks a school up by name, and another user's row is `failed`.
- **Figures arrive formatted** ("4.6%", "$85,960"), so the model never converts a ratio itself, and each with
  its reference period. A withheld or unavailable figure has no value.
- **Caveats travel with the reply.** The chat response carries `caveats`, the US federal caveats of every
  figure read that turn, and the desk shows them under Tassel's reply. `disclosure.warehouseReads` records
  each lookup.

Choices built into the schemas:

- **Matching a school name:** `universityName` is the student's wording. It is linked to a warehouse
  university only on an exact name or alias match, and otherwise kept as the student's own name. Never by
  fuzzy match (CLAUDE.md, "Entity resolution traps").
- **Reach/target/safety:** `userBand` is set only if the student used the word themself.
- **Deadlines:** the model may not supply a deadline from memory.
- **Theme evidence:** each quote must be copied verbatim from the student's message or essay. The API checks
  every quote against its source and drops any it cannot find. A theme left with no evidence is not stored,
  which matches the `user_theme` CHECK in V003.
- **Strict mode:** the schemas are closed (`additionalProperties: false`). They use `format`, `minItems` and
  `maxLength`, which not every provider's strict mode supports, so the API validates every call itself and
  does not rely on the provider to.

## What the tests hold

- `TasselChatIntegrationTest` (22): the loop with a scripted model; applied, proposed and failed calls; undo, confirm and reject; another user's rows; the exact-name rule; the round limit; no scores in the context; a federal lookup that is found (no action card, no `chat_action` row, figures with periods, its caveats), `none` and another user's school.
- `tasselPrompt.test.ts`:
  - the prompt states every rubric dimension exactly as `essay_rubric.json` defines it;
  - it names each tool, and no tool that does not exist;
  - it keeps the rules against admission chances, numeric scores, invented facts and claimed saves;
  - the tools that change something are exactly V004's allow-list (the read-only lookup is not on it), every
    tool has a policy entry, and every object schema is closed with its required fields present;
  - the prompt keeps the rule that an admission rate is not the student's chance.
- `TasselToolsContractTest`:
  - the stage, round, band and priority enums equal what `DeskTargetService` and `DeskTaskService` accept,
    in both directions;
  - the names of the tools that change something equal the database allow-list.
