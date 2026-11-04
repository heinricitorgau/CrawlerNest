# "Your desk": schema and API design

Status, 2026-10-18: **everything below is live.** On `/desk`, every card reads the API, and none holds sample
data:

- the chat is Tassel (`/api/v1/user/desk/chat`, below), and its changes show as cards with undo or confirm;
- the sprint with its tasks, application deadlines, and skills with practice logging;
- essay review, and the narrative themes with resonance.

DDL: [`V003__create_desk_schema.sql`](../../crawlernest/servise_for_java/src/main/resources/db/auth/V003__create_desk_schema.sql).
`AuthSchemaInitializer` runs that file at startup, after it creates `warehouse.app_user`. Unlike V001 and V002,
the DDL is not repeated inline in Java, so there is one copy. `DeskSchemaIntegrationTest` covers the constraints
described below against a real PostgreSQL.

## Decisions that shape everything else

1. **PostgreSQL only.** The warehouse, the auth tables and every schema file in this repo are PostgreSQL,
   and the user tables reference `warehouse.app_user` and `warehouse.canonical_university`. A MySQL copy
   would be a second database with no foreign keys to either. The table at the end lists what a port would
   have to change.
2. **New schema `desk`, written only by the Spring Boot API. Its only foreign key outside `desk` is to
   `warehouse.app_user`.** `target_entity.canonical_university_id` has no foreign key to
   `canonical_university`, just as `warehouse.saved_university` has none. The API starts against databases
   the pipeline has not bootstrapped (CI's starts empty), and a reference to a pipeline table would stop it
   starting. `merge_duplicate_canonicals.py` repoints the column, and its `verify` phase checks it. The Python agent keeps having no database
   connection (see `db/auth/V002__create_saved_conversation.sql`). Function calling does not change that.
   The model *returns* a tool call, and the API validates it and performs the write.
3. **There is no admission-probability column.** The warehouse holds published requirement thresholds
   (`admission_record`: IELTS, TOEFL, GPA, deadline). It holds no admit rates and no admitted-class
   profiles. Any percentage would be a number the model invented, which breaks the "no black-box scores"
   rule. What the API returns instead:
   - a **requirement check**, computed mechanically: each self-reported score against each published
     threshold, giving `meets` / `below` / `unknown`;
   - the **reach/target/safety band**, which is the user's own choice and is labelled as such.

   A real estimate needs an admit-rate source first, which would mean a new crawler.
4. **AI output is marked as AI output in the schema.** `user_theme`, `entity_resonance` and
   `essay_review` store the model name and the prompt or rubric version. Each also has `is_estimated`
   pinned `TRUE` by a CHECK, which is the same field `analytics.ml_predictions` uses to arm the provenance
   rule. A theme cannot be stored without evidence quoted from the user's own material.
5. **Numbers that can be computed are not left to the model.**
   - `skill_mastery.mastery_pct` is a generated column, `correct / attempted`.
   - `essay_review.overall_score` is computed by the API from the model's per-dimension scores, using the
     rubric's fixed weights.
   - Resonance is a 1–5 ordinal, not a percentage. The model can rank, but it cannot measure 73 against 71.
6. **One user's row cannot reference another user's row.** Each child table references its parent by
   `(id, user_id)`, so a wrong id in the service layer fails the insert instead of leaking data.
7. **Wikipedia text is never an input** to themes or resonance (CLAUDE.md, "Wikipedia introductions").
   The school side of a resonance row comes from either the user's notes or the model's general knowledge,
   and `institution_basis` records which.

## Tables

| Requested | Table | Notes |
|---|---|---|
| `users` | `warehouse.app_user` (existing) + `desk.user_profile` | Identity stays where it is. The profile adds settings and **self-reported** scores. |
| `tasks` | `desk.task`, `desk.sprint` | Priority `high/normal/low`. Status `todo/in_progress/done/cancelled`. `done` requires `completed_at`. A task created by the agent must point at its `chat_action`. |
| `target_entities` | `desk.target_entity` | Optional `canonical_university_id`, with no FK (otherwise `custom_name`). Has `stage`, `application_round`, a user-chosen `user_band`, and the user's own `deadline`. The published deadline is joined at read time, never copied. |
| `user_themes` | `desk.user_theme` | `suggested → accepted/dismissed`, and only the user can change it. Evidence array must be non-empty. |
| `entity_resonance` | `desk.entity_resonance` | One row per (theme, target). `level` 1–5, plus `rationale` and `institution_basis`. |
| `skill_mastery` | `desk.skill_mastery` | Unique per (user, subject, unit). Mastery is computed from the counts. |
| `essay_reviews` | `desk.essay_review` | A redraft is a new row with `revision_of_id`. Dimension scores and suggested edits are JSONB. Identical drafts are deduplicated by `draft_sha256`. |
| (new) | `desk.chat_action` | Audit trail for function calling: every write the model asked for, and what happened to it. |

Rows reach every table only through endpoints that take `user_id` from the session, never from the request
body (`docs/USER_DATA_SAFETY_REVIEW.md`).

## API

Base path `/api/v1/...`, like every Spring Boot route. Next.js already proxies `/api/*` to it. The
requested paths map one to one: `/api/chat/message` becomes `/api/v1/chat/message`, and so on. All
endpoints require the session cookie and return `401` without it.

Envelope: the existing `ApiResponse` (`success`, `data`, `metadata`). Errors use
`{"success": false, "error": {"code": "...", "message": "..."}}`. Responses that contain model output carry a
`caveats` array, and each estimated value keeps `isEstimated`.

### Tassel: `/api/v1/user/desk/chat/*` (implemented)

Code: `clawer.desk.chat` (`TasselChatService`, `TasselToolExecutor`, `ChatActionService`) and
`ChatController`. The design draft put this at `/api/v1/chat/message` and had Spring Boot call the agent API
on `:8090`. As built, it sits under `/api/v1/user/desk` like the rest of the desk, and Spring Boot calls the
model itself through the shared `DeskModelClient`. The Python agent stays out of the write path.

| Method and path | What it does |
|---|---|
| `POST /chat/message` | One turn. Body: `{"sessionId", "message", "history"?: [{"role": "user" \| "assistant", "content"}], "mode"?: "general" \| "brainstorming" \| "review"}`. |
| `GET /chat/actions?sessionId=` | A session's recorded actions, for this user only. |
| `POST /chat/actions/{id}/confirm` and `.../reject` | Decide a `proposed` action. |
| `POST /chat/actions/{id}/undo` | Reverse an `applied` action, within 24 hours. |

**One turn:**

1. The system prompt is `prompts/tassel_system.txt` followed by a context block built from the user's own
   desk: today in their time zone, the mode, open tasks, schools and essay titles, each with its id. It
   holds no scores, because Tassel gives none in chat.
2. The model is called with the browser-sent history (at most 20 turns), the new message, and the tools in
   `prompts/tassel_tools.json`.
3. `TasselToolExecutor` handles each tool call, validating it with the desk forms' rules. It writes a
   `desk.chat_action` row whether the call succeeds or fails, then applies the call, proposes it, or refuses
   it. The result goes back to the model as a `tool` message with the status first.
4. Steps 2 and 3 repeat until the model answers without a tool call: at most 3 tool rounds, and 5 calls per
   turn. When the limit stops it, the reply says so.

The conversation itself is not stored, only the actions. The browser holds the history.

**What each tool does when it runs:**

| Tool | Outcome |
|---|---|
| `create_action_task` | Applied: a task with `created_by = 'agent'` and `source_action_id`. A due date before today, in the user's time zone, fails. |
| `update_target_list` `add` | Applied. The name links to a warehouse university only on a unique, case- and spacing-insensitive exact match of the display name, native name or alias; a trailing all-caps parenthetical such as "(MIT)" is ignored. Merged records never match. Otherwise the user's wording is kept as `custom_name`. |
| `update_target_list` `update` / `remove` | Proposed. Applied only on `confirm`, through `DeskTargetService`. Another user's school fails. |
| `lookup_us_federal_data` | Read only, not recorded. Reads the US federal record of the warehouse university the user's own target links; `found`, `none` or `failed`. Its caveats are returned in `caveats`. |
| `generate_narrative_themes` | Applied as `suggested` themes. Each quote must occur in one of the user's messages this turn, or in an essay draft they own. Unmatched quotes are dropped, and a theme left with no quote is dropped. |

**Response** (`data`):

```json
{
  "turnIndex": 6,
  "reply": { "text": "...", "paragraphs": ["..."] },
  "actions": [
    { "id": "c2b1e7d4-...", "tool": "create_action_task", "status": "applied",
      "message": "Added the task \"Send SAT scores to MIT\", due 2026-10-25.",
      "arguments": { "...": "..." }, "result": { "table": "task", "id": 812 } }
  ],
  "caveats": [],
  "disclosure": { "model": "...", "userDataWrites": [{ "table": "desk.task", "id": 812 }],
                  "warehouseWrites": false, "pipelineRuns": false,
                  "warehouseReads": [] }
}
```

`caveats` holds the caveats of the US federal figures read this turn (`lookup_us_federal_data`), once each;
`disclosure.warehouseReads` lists those lookups (`tool`, `status`, `targetEntityId`, `canonicalUniversityId`,
`unitid`). Both are empty when nothing was read.

**Change from the draft:** the draft said the API would check the reply text against the action statuses and
append a correction. As built, it does not parse prose. Instead, two things keep the outcome honest:

- the model is given each real status before it writes the reply;
- the UI draws every action from its status as a card under the reply (Done, Waiting for you,
  Didn't happen), with Undo, Confirm or Reject.

A reply that misstated an outcome would be contradicted on the same screen.

Tests: `TasselChatIntegrationTest` (16, with a scripted model) and `TasselChat.test.tsx`. The whole loop was
also run against a fake OpenAI-compatible server: tool calls in the wire format, results returned by
`tool_call_id`, then undo.

### Narrative: `/api/v1/user/desk/story/*` (implemented)

Code: `clawer.desk.story.NarrativeService` and `NarrativeController`. It is under `/api/v1/user/desk` for the
same reason as the rest of the desk.

| Method and path | What it does |
|---|---|
| `GET /story/narrative?includeDismissed=` | Read-only. Returns themes (accepted first, then suggested), resonance for accepted themes, and caveats. What the desk page reads. |
| `GET /story/themes?includeDismissed=` | Read-only. The themes alone, with the narrative caveat. |
| `GET /story/resonance` | Read-only. Accepted themes' 1–5 levels against the user's schools, each with its rationale and `institutionBasis`, plus the `scale` and the caveats that apply. |
| `POST /story/generate` (alias: `/story/themes/generate`) | Draws one or two themes from the user's drafts: the latest draft of each essay, up to 6 drafts and 40,000 characters. Replaces open suggestions; never touches an accepted theme. The two paths are one handler. |
| `PATCH /story/themes/{id}` | `{"status": "accepted" \| "dismissed"}`. Dismissing drops that theme's resonance rows. |
| `POST /story/resonance/generate` | Judges each accepted theme (up to 3) against each school on the list that is not rejected or withdrawn (up to 12). Replaces earlier judgements for those themes. |

Every response is the whole narrative, so the page never shows themes and resonance from two different
moments.

What is checked by CrawlerNest, not taken from the model:

- **Theme evidence.** Each quote must occur verbatim in the draft it names (`draftId`), and the model sees
  only this user's drafts. Unmatched quotes are dropped. A theme with none left is dropped. If no theme
  survives, the endpoint answers 502 and nothing is stored.
- **Where the school side came from (`institution_basis`).** A school with no notes from the user is always
  `model_general_knowledge`, whatever the model says. `user_notes` is kept only when the notes exist.
- **Ids and levels.** Ids must be among the themes and schools sent. Levels must be whole numbers from 1
  to 5. Anything else is skipped, and `missingPairs` reports how many pairs got no usable judgement.
- **Inputs.** The resonance prompt forbids admission chances, acceptance rates, rankings and deadlines.
  Wikipedia text is never an input.

Prompts: `prompts/narrative_themes_system.txt` (`narrative-themes-2026.1`) and `prompts/resonance_system.txt`
(`resonance-2026.1`). Every row stores its model and prompt version and carries `isEstimated: true`.

Caveats, under the caveat contract:

- `NARRATIVE_ESTIMATE_CAVEAT` is always present.
- `RESONANCE_GENERAL_KNOWLEDGE_CAVEAT` is added when any row's basis is the model's general knowledge.

Response (`data`):

```json
{
  "themes": [
    { "id": 17, "title": "The Builder Who Teaches", "summary": "...", "traits": ["Maker", "Mentor"],
      "status": "accepted",
      "evidence": [{ "kind": "essay_review", "refId": "318", "quote": "I rebuilt the arm three times." }],
      "isEstimated": true,
      "provenance": { "model": "...", "promptVersion": "narrative-themes-2026.1", "generatedAt": "..." } }
  ],
  "resonance": [
    { "themeId": 17, "targetEntityId": 41, "institution": "Notes College", "level": 4, "levelLabel": "Strong",
      "rationale": "...", "institutionBasis": "user_notes", "isEstimated": true, "provenance": { "...": "..." } }
  ],
  "caveats": ["Narrative themes and resonance levels are a language model's reading of ..."],
  "missingPairs": 0
}
```

`missingPairs` is present only on `resonance/generate`. Level labels: 5 and 4 are `Strong`, 3 is
`Moderate`, 2 and 1 are `Emerging`. The UI's `ResonanceBar` draws the 1–5 level as five segments.

**Where the material comes from.** `POST /story/generate` reads the user's essay drafts only. Chat
conversations are not stored server-side (the browser holds the history), so they cannot be re-read later.
Themes from conversation come from Tassel's `generate_narrative_themes` tool during the turn, with each quote
checked against that turn's own messages. Reading conversations here would need transcripts stored first,
and that is a separate decision.

**Column names.** The schema uses `title` / `summary` (themes) and `level` / `rationale` (resonance). A spec
written against `theme_title` / `description` / `resonance_level` / `reasoning_text` means the same columns.

Tests: `NarrativeApiIntegrationTest` (16), `NarrativeControllerTest` (8, controller contract with the
service mocked) and `LiveNarrativeCard.test.tsx`.

### `POST /api/v1/user/desk/essays/evaluate` (implemented)

Under `/api/v1/user/desk`, like the CRUD endpoints, so the filter chain closes it. Also on that path:
`GET /essays`, `GET /essays/{id}` and `DELETE /essays/{id}`. Code: `clawer.desk.essay`.

**Who calls the model:** the Spring Boot API calls the model itself (`OpenAiCompatibleModelClient`).
It is not the browser or the Next route, because then the API would have to accept scores from a caller,
and a caller could make them up. The API reads the same variables as the Next agent route
(`AGENT_MODEL_PROVIDER`, `AGENT_MODEL_NAME`, `AGENT_MODEL_BASE_URL`, `OPENAI_API_KEY`, `OLLAMA_BASE_URL`,
`WEB_AGENT_DS4_*`), so one setting configures both. With the default `mock` there is no model, and the
endpoint answers `503 MODEL_UNAVAILABLE` rather than inventing scores.

**Rubric:** `servise_for_java/src/main/resources/prompts/essay_rubric.json` (`essay-rubric-2026.1`):

| Dimension | Weight |
|---|---|
| impact | 0.25 |
| introspection | 0.25 |
| passion | 0.25 |
| originality | 0.25 |

The rubric also defines the score bands. The scorer's system prompt (`essay_scoring_system.txt`) is
rendered from that file, and Tassel's review section copies its definitions (`tasselPrompt.test.ts` checks
they agree).

**What CrawlerNest does with the model's reply, not the model:**

- **Overall score:** the weighted mean of the dimension scores. The model is told not to give one.
- **Offsets:** the model returns quotes, not positions. `EssayEvaluator` finds each quote in the draft. A
  quote that is not there verbatim, or occurs more than once, is dropped and counted in `droppedQuotes`; it
  is never highlighted at a guessed position.
- **Unreadable replies:** a reply that is not JSON, or is missing a dimension, or has a score that is not a
  whole number from 0 to 100, gets one retry with the problem named. If the retry also fails, the endpoint
  answers `502 MODEL_REPLY_UNREADABLE`. Nothing partial is stored.
- **Untrusted essay text:** the essay is sent between `<essay>` tags, and the prompt says to treat anything
  inside as text to judge, not as instructions.
- **Unchanged drafts:** a draft whose SHA-256 the user already has stored under the same rubric version
  returns the stored review with `"cached": true`, without a model call. Otherwise the model's own variance
  would look like the essay changing.

Request: `{"essayTitle", "essayPrompt"?, "targetEntityId"?, "revisionOfId"?, "draftText"}`.

- `draftText` is 1 to 20,000 characters and is stored untrimmed, so offsets match what was sent.
- An unknown field is a 400. That includes any attempt to send scores.
- Another user's `targetEntityId` or `revisionOfId` answers 400.

Response (`data`):

```json
{
  "id": 318, "essayTitle": "Personal statement", "essayPrompt": null, "targetEntityId": null,
  "revisionOfId": 305, "cached": false, "draftText": "...", "wordCount": 642,
  "rubricVersion": "essay-rubric-2026.1",
  "overall": { "score": 73.8, "method": "weighted_mean",
               "weights": { "impact": 0.25, "introspection": 0.25, "passion": 0.25, "originality": 0.25 } },
  "dimensions": [
    { "key": "impact", "label": "Impact", "score": 82, "rationale": "...", "evidence": [{ "start": 120, "end": 188 }] },
    { "key": "introspection", "label": "Introspection", "score": 64, "rationale": "...", "evidence": [] },
    { "key": "passion", "label": "Passion", "score": 78, "rationale": "...", "evidence": [] },
    { "key": "originality", "label": "Originality", "score": 71, "rationale": "...", "evidence": [] }
  ],
  "suggestions": [
    { "start": 412, "end": 458, "original": "I learned that failure is part of engineering.",
      "suggested": "I stopped hiding the broken prototypes [when did that start?].",
      "dimension": "introspection", "reason": "Show the change in behaviour rather than stating the lesson." }
  ],
  "comparedToRevision": { "id": 305, "overallDelta": 4.1,
                          "dimensionDeltas": { "impact": 3, "introspection": 9, "passion": 0, "originality": 2 } },
  "droppedQuotes": 1,
  "isEstimated": true,
  "provenance": { "model": "gpt-4.1-mini", "evaluatedAt": "2026-10-18T08:43:21Z" },
  "caveats": ["Essay scores are a language model's reading of this draft ...",
              "The overall essay score is the rubric-weighted mean of the dimension scores, ..."]
}
```

- `comparedToRevision` is null when the two drafts were scored under different rubric versions, because
  their scores are on different scales.
- `droppedQuotes` is present only on a fresh evaluation.
- Both caveats are under the caveat contract (`test_caveat_contract.py`).

Tests:

- `EssayEvaluatorTest` (10): anchoring, invented and ambiguous quotes, fenced JSON, retry, refusal, the
  weighted mean.
- `EssayApiIntegrationTest` (9): through the filter chain to PostgreSQL, with the model mocked.
- `EssayReview.test.tsx`.

On `/desk`, the Essay review tab submits drafts, and "Your desk" shows the latest review in brief.

## CRUD endpoints (implemented)

`DeskController`, under `/api/v1/user/desk`. The path is not the `/api/v1/desk` the first draft used:
`SecurityConfig` closes `/api/v1/user/**` to anonymous callers at the filter chain, so a new endpoint there
is closed by default. A route outside that prefix would be public unless every handler remembered to
check. The browser reaches these endpoints through the Next proxy at `/api/user/desk/**`
(`app/api/user/desk/[...path]/route.ts`). The proxy forwards lower-case path segments and numeric ids
only, at most three segments, plus an allow-list of query parameters.

| Method and path | Notes |
|---|---|
| `GET /tasks?status=open\|done\|all&sprintId=` | Default `open`. Ordered open first, then soonest due, undated last. |
| `GET /tasks/{id}`, `POST /tasks`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}` | `completedAt` follows `status`. Tasks created here are `createdBy: "user"`. |
| `GET /sprints`, `GET /sprints/current`, `GET /sprints/{id}` | `current` is the sprint covering today in the profile's time zone; `data: null` when none does. |
| `POST /sprints`, `PATCH /sprints/{id}`, `DELETE /sprints/{id}` | Deleting a sprint keeps its tasks and clears their `sprintId`. |
| `GET /targets?stage=`, `GET /targets/{id}`, `POST /targets`, `PATCH /targets/{id}`, `DELETE /targets/{id}` | `name` is the warehouse display name when linked. A missing university is refused, and so is a `merged` one. A repeated (university, programme) pair answers 409; the programme comparison ignores case and spacing. |
| `GET /skills?subject=`, `POST /skills/results`, `DELETE /skills/{id}` | Results add to a unit's counts. No endpoint accepts a percentage. A result from a different `source` than the unit's answers 409. |
| `GET /profile`, `PUT /profile` | `GET` returns defaults and never writes. `PUT` replaces the whole profile. Scores are nested under `selfReported`. Every save increments `revision` (`0` until the first save). A `PUT` with `expectedRevision` is applied only if the stored profile is still at that revision and answers 409 otherwise, so a stale tab cannot overwrite a newer save; `expectedRevision: 0` creates the profile only if none exists. Without `expectedRevision` the write is unconditional (V007). |

Conventions:

- Bodies are read field by field, and an unknown field is a 400 that names it.
- In a `PATCH`, an absent field is left alone and a `null` field is cleared.
- Tasks, targets, sprints and the profile carry a `revision` (V007, V008). A `PATCH /tasks/{id}`, `/targets/{id}` or
  `/sprints/{id}` with `expectedRevision` is applied only if the row is still at that revision, and answers 409
  otherwise; without it the write is unconditional. A sprint's revision covers its own fields, not its tasks. Task,
  target and sprint revisions are counted by a trigger, so a change that does not pass
  through the API (a deleted sprint or target clearing a task's link, a canonical merge repointing a target) also
  makes a stale copy stale. Another user's row is still a 404, never a 409.
- Another user's id answers 404, the same as a missing row.
- An id in a body that belongs to someone else (`sprintId`, `targetEntityId`) answers 400
  (`"No such sprint."`).
- Error bodies are `{"success": false, "error": "..."}`, as the other user controllers return them.

Tests: `DeskApiIntegrationTest` (17, filter chain through to PostgreSQL), `deskProxyRoute.test.ts` and
`LiveDeskCards.test.tsx`.

## Implementation order

1. ~~Move the DDL into `V003__create_desk_schema.sql` and apply it through `AuthSchemaInitializer`.~~ Done.
2. ~~Add the CRUD endpoints (tasks, targets, skills), then point the desk cards at them.~~ Done. The
   College list tab (`CollegeListPanel`) adds and removes schools and edits each school's stage, round,
   deadline, label and notes. Notes are what `resonance/generate` judges from; a fit judged from them is
   stored as `user_notes`. After a save, the desk's cards re-read the list.
3. ~~Add `essays/evaluate`, then `story/*`, then the `chat/message` tool loop.~~ Done
   (`docs/agent/TASSEL_ASSISTANT.md`).
4. New caveat strings go through the caveat contract: `crawlernest/core/caveats.py`, the
   `AnalyticsService` constants, `caveatMessages.ts` and `ANALYTICS_EXPLAINABILITY.md`.
   `test_caveat_contract.py` checks that all four agree. The essay and narrative caveats are in all four.

## If it ever has to run on MySQL 8

| PostgreSQL | MySQL 8 |
|---|---|
| schema `desk` | a separate database, with no cross-database FK to `app_user` (lost) |
| `JSONB` + `jsonb_typeof` CHECKs | `JSON` + `JSON_TYPE()` CHECKs |
| `TEXT[]` (`traits`) | `JSON` array |
| `GENERATED ALWAYS AS (...) STORED` | supported, same syntax |
| partial indexes (`WHERE status IN ...`) | not supported: full index, or a generated column to index |
| `ON DELETE SET NULL (col)` on composite FKs | not supported: SET NULL would null `user_id` too, so use an application-side cleanup or a trigger |
| `UUID` | `BINARY(16)` or `CHAR(36)` |
| `TIMESTAMPTZ` | `TIMESTAMP` (stored as UTC; the session time zone matters) |
