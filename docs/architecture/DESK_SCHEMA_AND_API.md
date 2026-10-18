# "Your desk": schema and API design

Status: **proposal, 2026-10-18.** None of this is applied or implemented. The `/desk` page
(`crawlernest-web/src/app/desk/`) already sends chat to `/api/agent/chat`; its cards hold sample data
until the tables and endpoints below exist.

DDL: [`desk_schema_postgresql.sql`](desk_schema_postgresql.sql). It was applied twice (it is idempotent) to a
throwaway PostgreSQL 16 database, and each constraint described below was exercised with an insert that
should pass and one that should fail.

## Decisions that shape everything else

1. **PostgreSQL only.** The warehouse, the auth tables and every schema file in this repo are PostgreSQL,
   and the user tables reference `warehouse.app_user` and `warehouse.canonical_university`. A MySQL copy
   would be a second database with no foreign keys to either. The table at the end lists what a port would
   have to change.
2. **New schema `desk`, written only by the Spring Boot API.** The Python agent keeps having no database
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
| `target_entities` | `desk.target_entity` | Optional link to `canonical_university` (otherwise `custom_name`). Has `stage`, `application_round`, a user-chosen `user_band`, and the user's own `deadline`. The published deadline is joined at read time, never copied. |
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

### `POST /api/v1/chat/message`

Flow:

1. Spring Boot receives the message.
2. It calls the agent API (`:8090`) with the message, the tool schemas below and a small context: the
   titles and ids of open tasks and targets.
3. The agent returns a reply plus zero or more tool calls.
4. Spring Boot checks each tool call against the allow-list and runs the same validation a form submit
   gets.
5. Each call is then **applied** or **proposed**:
   - **applied:** additive and reversible actions, `create_task` and `add_target_entity`;
   - **proposed:** changes to an existing record, `update_task_status` and `update_target_stage`. The user
     confirms these.

Every call gets a `chat_action` row, including ones that fail validation.

Request:

```json
{
  "sessionId": "8a3f2c1e-5b7d-4e09-9c61-2f4d8b0a7e15",
  "message": "Remind me to finish my MIT supplement by Oct 25, and move Stanford to applying."
}
```

Response `200`:

```json
{
  "success": true,
  "data": {
    "turnIndex": 6,
    "reply": {
      "text": "Added a task for the MIT supplement, due Oct 25. Moving Stanford to \"applying\" changes your list, so confirm it below.",
      "paragraphs": [
        "Added a task for the MIT supplement, due Oct 25.",
        "Moving Stanford to \"applying\" changes your list, so confirm it below."
      ]
    },
    "actions": [
      {
        "id": "c2b1e7d4-0f3a-4a8e-b5c9-71d2e6f0a934",
        "tool": "create_task",
        "status": "applied",
        "arguments": { "title": "Finish MIT supplement", "dueDate": "2026-10-25", "priority": "high", "targetEntityId": 41 },
        "result": { "table": "task", "id": 812 },
        "undoUrl": "/api/v1/chat/actions/c2b1e7d4-0f3a-4a8e-b5c9-71d2e6f0a934/undo"
      },
      {
        "id": "5e9d0a6b-3c2f-4f71-8a1e-0b7c4d9e2f58",
        "tool": "update_target_stage",
        "status": "proposed",
        "arguments": { "targetEntityId": 44, "from": "shortlisted", "to": "applying" },
        "result": null,
        "confirmUrl": "/api/v1/chat/actions/5e9d0a6b-3c2f-4f71-8a1e-0b7c4d9e2f58/confirm",
        "rejectUrl": "/api/v1/chat/actions/5e9d0a6b-3c2f-4f71-8a1e-0b7c4d9e2f58/reject"
      }
    ],
    "warnings": [],
    "disclosure": {
      "model": "gpt-4.1-mini",
      "userDataWrites": [{ "table": "desk.task", "id": 812 }],
      "warehouseWrites": false,
      "pipelineRuns": false
    }
  },
  "metadata": { "timestamp": "2026-10-18T08:41:07Z" }
}
```

- `warnings` passes the agent's coded disclosures through unchanged, for `AgentWarningBanner`.
- `disclosure` replaces the old route's `dbWrites: false`, which becomes untrue once this route writes
  anything. It lists exactly which user rows changed, and states that the warehouse was not touched.
- A tool call that fails validation comes back with `"status": "failed"` and the validation message in
  `result`. The reply text must not claim it succeeded: the API checks that the model's text and the
  action statuses agree, and appends a correction if they do not.

Companion endpoints:

- `POST /api/v1/chat/actions/{id}/confirm`, `.../reject` and `.../undo`. Undo works on `applied` actions
  for 24 hours.
- `GET /api/v1/desk/tasks?status=open` and `GET /api/v1/desk/targets`. These are plain CRUD and are not
  specified further here.

Tool schemas sent to the model (also the server-side validation):

| Tool | Arguments | Default |
|---|---|---|
| `create_task` | `title` (1–200), `dueDate?` (ISO date, not in the past), `priority?`, `category?`, `targetEntityId?` (must be the user's) | applied |
| `add_target_entity` | `canonicalUniversityId?` or `customName?`, `programmeName?`, `stage?` | applied |
| `update_task_status` | `taskId`, `status` | proposed |
| `update_target_stage` | `targetEntityId`, `stage` | proposed |

### `GET /api/v1/story/narrative`

This endpoint is read-only. It returns the user's themes (accepted and suggested; add `?includeDismissed=true`
for dismissed ones too) and the resonance between each theme and each target.

Response `200`:

```json
{
  "success": true,
  "data": {
    "themes": [
      {
        "id": 17,
        "title": "The Builder Who Teaches",
        "summary": "You make things, then turn what you learned into something others can use.",
        "traits": ["Maker", "Mentor", "Systems thinker"],
        "status": "accepted",
        "evidence": [
          { "kind": "essay_review", "refId": "305", "quote": "I rebuilt the arm three times before I let the freshmen touch it." },
          { "kind": "user_note", "refId": "note-12", "quote": "Run a weekend coding club for 14 middle schoolers." }
        ],
        "isEstimated": true,
        "provenance": { "model": "gpt-4.1-mini", "promptVersion": "themes-v2", "generatedAt": "2026-10-16T13:02:44Z" }
      }
    ],
    "resonance": [
      {
        "themeId": 17,
        "targetEntityId": 41,
        "institution": "Massachusetts Institute of Technology",
        "level": 5,
        "levelLabel": "Strong",
        "rationale": "Hands-on building is the core of both your evidence and the programme you noted.",
        "institutionBasis": "user_notes",
        "isEstimated": true,
        "provenance": { "model": "gpt-4.1-mini", "promptVersion": "resonance-v1", "generatedAt": "2026-10-16T13:03:10Z" }
      },
      {
        "themeId": 17,
        "targetEntityId": 47,
        "institution": "California Institute of Technology",
        "level": 2,
        "levelLabel": "Emerging",
        "rationale": "Few examples of community impact yet.",
        "institutionBasis": "model_general_knowledge",
        "isEstimated": true,
        "provenance": { "model": "gpt-4.1-mini", "promptVersion": "resonance-v1", "generatedAt": "2026-10-16T13:03:10Z" }
      }
    ],
    "caveats": [
      "Themes and resonance levels are model estimates drawn from what you have written here. They are not an admissions assessment.",
      "Resonance marked model_general_knowledge describes the institution from the model's general knowledge, not from CrawlerNest data."
    ]
  },
  "metadata": { "timestamp": "2026-10-18T08:42:00Z" }
}
```

Level labels: 5–4 is `Strong`, 3 is `Moderate`, 2–1 is `Emerging`. The UI's `ResonanceBar` takes
`level × 20`. Generating themes is a separate write, `POST /api/v1/story/themes/generate`, and
`PATCH /api/v1/story/themes/{id}` accepts or dismisses a theme.

### `POST /api/v1/essays/evaluate`

Synchronous, with a 60 s timeout. A draft identical to an earlier one, under the same rubric, returns the
stored review with `"cached": true` and does not call the model again.

Request:

```json
{
  "essayTitle": "Personal statement",
  "essayPrompt": "Describe a challenge you overcame.",
  "targetEntityId": 41,
  "revisionOfId": 305,
  "draftText": "The first time the robot arm failed, ..."
}
```

Validation: `draftText` 1–20,000 characters; `targetEntityId` and `revisionOfId` must belong to the user;
otherwise `400`.

Response `200`:

```json
{
  "success": true,
  "data": {
    "id": 318,
    "revisionOfId": 305,
    "cached": false,
    "wordCount": 642,
    "rubricVersion": "essay-rubric-2026.1",
    "overall": {
      "score": 78.4,
      "method": "weighted_mean",
      "weights": { "impact": 0.3, "introspection": 0.3, "voice": 0.2, "structure": 0.2 }
    },
    "dimensions": [
      { "key": "impact", "label": "Impact", "score": 82, "rationale": "The stakes are concrete and personal.", "evidence": [{ "start": 120, "end": 188 }] },
      { "key": "introspection", "label": "Introspection", "score": 64, "rationale": "Says what happened more than what changed in you.", "evidence": [{ "start": 402, "end": 470 }] },
      { "key": "voice", "label": "Voice", "score": 85, "rationale": "Distinct and consistent.", "evidence": [] },
      { "key": "structure", "label": "Structure", "score": 79, "rationale": "Clear arc; the ending is abrupt.", "evidence": [{ "start": 590, "end": 642 }] }
    ],
    "suggestions": [
      {
        "start": 412,
        "end": 470,
        "original": "I learned that failure is part of engineering.",
        "suggested": "I stopped hiding the broken prototypes and started showing them to the freshmen first.",
        "dimension": "introspection",
        "reason": "Show the change in behaviour rather than stating the lesson."
      }
    ],
    "comparedToRevision": {
      "id": 305,
      "overallDelta": 4.1,
      "dimensionDeltas": { "impact": 3, "introspection": 9, "voice": 0, "structure": 2 }
    },
    "isEstimated": true,
    "provenance": { "model": "gpt-4.1-mini", "evaluatedAt": "2026-10-18T08:43:21Z" },
    "caveats": [
      "Scores are a model's reading of this draft against the CrawlerNest rubric, not a prediction of how an admissions reader will score it.",
      "The overall score is the rubric-weighted mean of the dimension scores."
    ]
  },
  "metadata": { "timestamp": "2026-10-18T08:43:21Z" }
}
```

- `start`/`end` are character offsets into the submitted `draftText`. The UI highlights them, and diffs
  two drafts by loading both rows.
- The API rejects a model response that points at offsets outside the text, or whose `original` does not
  equal `draftText[start:end]`, and retries once. A suggestion that cannot be anchored is dropped, never
  shown at a guessed position.
- `503` with `"code": "MODEL_UNAVAILABLE"` if the provider is down. Nothing is stored in that case.

## Implementation order

1. Move the DDL into `servise_for_java/src/main/resources/db/auth/V003__create_desk_schema.sql` and apply
   it through `AuthSchemaInitializer`, as V001 and V002 are.
2. Add the CRUD endpoints (tasks, targets, skills), then point the desk cards at them and remove the
   sample banner card by card.
3. Add `essays/evaluate`, then `story/*`, then the `chat/message` tool loop. The tool loop goes last
   because it depends on the CRUD validation.
4. New caveat strings go through the caveat contract: `crawlernest/core/caveats.py`, the
   `AnalyticsService` constants, `caveatMessages.ts` and `ANALYTICS_EXPLAINABILITY.md`.
   `test_caveat_contract.py` checks that all four agree. The texts above are drafts.

## If it ever has to run on MySQL 8

| PostgreSQL | MySQL 8 |
|---|---|
| schema `desk` | a separate database, with no cross-database FKs to the warehouse (lost) |
| `JSONB` + `jsonb_typeof` CHECKs | `JSON` + `JSON_TYPE()` CHECKs |
| `TEXT[]` (`traits`) | `JSON` array |
| `GENERATED ALWAYS AS (...) STORED` | supported, same syntax |
| partial indexes (`WHERE status IN ...`) | not supported: full index, or a generated column to index |
| `ON DELETE SET NULL (col)` on composite FKs | not supported: SET NULL would null `user_id` too, so use an application-side cleanup or a trigger |
| `UUID` | `BINARY(16)` or `CHAR(36)` |
| `TIMESTAMPTZ` | `TIMESTAMP` (stored as UTC; the session time zone matters) |
