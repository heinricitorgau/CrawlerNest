-- =========================================================
-- CrawlerNest "Your desk" schema (PostgreSQL)
-- =========================================================
--
-- AuthSchemaInitializer runs this file at application startup, after the
-- warehouse.app_user table it references. Unlike V001/V002 it is not mirrored
-- inline in Java: the initializer reads this file, so there is one copy.
-- Design and reasons: docs/architecture/DESK_SCHEMA_AND_API.md.
--
-- Every statement must be idempotent (IF NOT EXISTS) and must not use
-- dollar-quoted blocks: Spring's script runner splits on ';'.
--
-- Requires: warehouse.app_user only. canonical_university_id carries no foreign
-- key, as warehouse.saved_university does not: the API starts against databases
-- the pipeline has not bootstrapped (CI's is empty), and a reference to a
-- pipeline table would stop it starting. merge_duplicate_canonicals.py repoints
-- the column when it merges two records.
--
-- Ownership: the Spring Boot API is the only writer, always for the
-- session-authenticated user. The Python agent has no database connection and
-- gets none from this design: when the model asks for a write (function
-- calling), it returns the request, and the API validates and performs it.
--
-- Isolation: every table carries user_id, and every child table references its
-- parent by (id, user_id), so a row cannot point at another user's row even if
-- the service layer gets an id wrong.
--
-- Nothing here is warehouse or analytics data, and nothing in the ranking
-- pipeline reads it. Losing it loses a user's planning notes, not published data.

CREATE SCHEMA IF NOT EXISTS desk;

-- ---------------------------------------------------------
-- users: profile and settings, one row per app_user
-- ---------------------------------------------------------
-- Identity stays in warehouse.app_user (email, password hash). This holds what
-- the desk needs on top of it. Scores are what the user typed in, labelled as
-- such: the API compares them to published requirements and never presents
-- them as verified.
CREATE TABLE IF NOT EXISTS desk.user_profile (
    user_id              BIGINT       PRIMARY KEY REFERENCES warehouse.app_user(id) ON DELETE CASCADE,
    display_name         VARCHAR(100),
    graduation_year      SMALLINT     CHECK (graduation_year BETWEEN 2000 AND 2100),
    timezone             VARCHAR(64)  NOT NULL DEFAULT 'UTC',
    locale               VARCHAR(16)  NOT NULL DEFAULT 'en',
    self_reported_gpa    NUMERIC(4,2) CHECK (self_reported_gpa >= 0),
    gpa_scale            NUMERIC(4,2) CHECK (gpa_scale > 0),
    self_reported_ielts  NUMERIC(2,1) CHECK (self_reported_ielts BETWEEN 0 AND 9),
    self_reported_toefl  SMALLINT     CHECK (self_reported_toefl BETWEEN 0 AND 120),
    self_reported_sat    SMALLINT     CHECK (self_reported_sat BETWEEN 400 AND 1600),
    -- UI settings only (theme, default tab, notification opt-ins). Nothing the
    -- API branches on for correctness belongs in here.
    preferences          JSONB        NOT NULL DEFAULT '{}'::jsonb
                                      CHECK (jsonb_typeof(preferences) = 'object'),
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT user_profile_gpa_needs_scale CHECK (self_reported_gpa IS NULL OR gpa_scale IS NOT NULL),
    CONSTRAINT user_profile_gpa_within_scale CHECK (self_reported_gpa IS NULL OR self_reported_gpa <= gpa_scale)
);

-- ---------------------------------------------------------
-- target_entities: the user's list of schools / programmes
-- ---------------------------------------------------------
-- Points at a warehouse university when there is one, so ranks and published
-- admission requirements can be joined in at read time. A target the warehouse
-- does not hold is kept by name.
--
-- There is no admission-probability column. The warehouse has requirement
-- thresholds (IELTS, TOEFL, GPA, deadline) but no admit rates or admitted-class
-- profiles, so any percentage would be a number the model made up. The API
-- returns a mechanical requirement check instead (see the spec), and the
-- reach/target/safety band is the user's own call.
CREATE TABLE IF NOT EXISTS desk.target_entity (
    id                       BIGSERIAL    PRIMARY KEY,
    user_id                  BIGINT       NOT NULL REFERENCES warehouse.app_user(id) ON DELETE CASCADE,
    canonical_university_id  BIGINT,       -- warehouse.canonical_university; no FK, see the header
    custom_name              VARCHAR(200),
    programme_name           VARCHAR(200),
    -- '' rather than NULL so the unique key below treats "no programme" as one value.
    programme_key            VARCHAR(200) NOT NULL DEFAULT '',
    stage                    VARCHAR(16)  NOT NULL DEFAULT 'researching'
                                          CHECK (stage IN ('researching', 'shortlisted', 'applying', 'submitted',
                                                           'admitted', 'waitlisted', 'rejected', 'enrolled', 'withdrawn')),
    application_round        VARCHAR(8)   CHECK (application_round IN ('ED', 'ED2', 'EA', 'REA', 'RD', 'rolling')),
    user_band                VARCHAR(8)   CHECK (user_band IN ('reach', 'target', 'safety')),
    -- The user's own deadline. The published one (admission_record.application_deadline)
    -- is joined at read time and shown beside it, never copied in.
    deadline                 DATE,
    notes                    TEXT,
    created_by               VARCHAR(8)   NOT NULL DEFAULT 'user' CHECK (created_by IN ('user', 'agent')),
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT target_entity_named CHECK (canonical_university_id IS NOT NULL OR custom_name IS NOT NULL),
    CONSTRAINT target_entity_id_user_key UNIQUE (id, user_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS target_entity_user_university_key
    ON desk.target_entity (user_id, canonical_university_id, programme_key)
    WHERE canonical_university_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS target_entity_user_stage_idx
    ON desk.target_entity (user_id, stage);

-- ---------------------------------------------------------
-- chat_action: every write the model asked for, and what became of it
-- ---------------------------------------------------------
-- The audit trail for function calling. The model proposes; the API checks the
-- tool against its allow-list and the arguments against the same validation a
-- form submit gets, then applies it or holds it for the user to confirm.
CREATE TABLE IF NOT EXISTS desk.chat_action (
    id            UUID         PRIMARY KEY,
    user_id       BIGINT       NOT NULL REFERENCES warehouse.app_user(id) ON DELETE CASCADE,
    session_id    VARCHAR(64)  NOT NULL,
    turn_index    INTEGER      NOT NULL CHECK (turn_index >= 0),
    -- The draft's tool names. V004 replaces this check with Tassel's; this stays so V003 is unchanged.
    tool_name     VARCHAR(40)  NOT NULL CHECK (tool_name IN ('create_task', 'update_task_status',
                                                             'add_target_entity', 'update_target_stage')),
    arguments     JSONB        NOT NULL CHECK (jsonb_typeof(arguments) = 'object'),
    status        VARCHAR(10)  NOT NULL CHECK (status IN ('applied', 'proposed', 'confirmed', 'rejected', 'undone', 'failed')),
    -- {"table": "task", "id": 812} once applied; the validation error when failed.
    result        JSONB,
    model_name    VARCHAR(100) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    decided_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS chat_action_user_session_idx
    ON desk.chat_action (user_id, session_id, turn_index);

-- ---------------------------------------------------------
-- tasks: to-dos with deadline, priority and status (and the sprint they sit in)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS desk.sprint (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT       NOT NULL REFERENCES warehouse.app_user(id) ON DELETE CASCADE,
    title       VARCHAR(120) NOT NULL,
    goal        VARCHAR(500),
    start_date  DATE         NOT NULL,
    end_date    DATE         NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT sprint_dates_ordered CHECK (end_date >= start_date),
    CONSTRAINT sprint_id_user_key UNIQUE (id, user_id)
);

CREATE TABLE IF NOT EXISTS desk.task (
    id                BIGSERIAL    PRIMARY KEY,
    user_id           BIGINT       NOT NULL REFERENCES warehouse.app_user(id) ON DELETE CASCADE,
    title             VARCHAR(200) NOT NULL CHECK (btrim(title) <> ''),
    notes             TEXT,
    due_date          DATE,
    priority          VARCHAR(8)   NOT NULL DEFAULT 'normal' CHECK (priority IN ('high', 'normal', 'low')),
    status            VARCHAR(12)  NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'done', 'cancelled')),
    category          VARCHAR(40),
    sprint_id         BIGINT,
    target_entity_id  BIGINT,
    created_by        VARCHAR(8)   NOT NULL DEFAULT 'user' CHECK (created_by IN ('user', 'agent')),
    -- The chat action that created it, when created_by = 'agent'; lets "undo" find it.
    source_action_id  UUID         REFERENCES desk.chat_action (id),
    completed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT task_sprint_same_user FOREIGN KEY (sprint_id, user_id)
        REFERENCES desk.sprint (id, user_id) ON DELETE SET NULL (sprint_id),
    CONSTRAINT task_target_same_user FOREIGN KEY (target_entity_id, user_id)
        REFERENCES desk.target_entity (id, user_id) ON DELETE SET NULL (target_entity_id),
    CONSTRAINT task_done_has_time CHECK ((status = 'done') = (completed_at IS NOT NULL)),
    CONSTRAINT task_agent_has_action CHECK (created_by = 'user' OR source_action_id IS NOT NULL)
);

-- The task panel: this user's open tasks, soonest first.
CREATE INDEX IF NOT EXISTS task_user_open_due_idx
    ON desk.task (user_id, due_date)
    WHERE status IN ('todo', 'in_progress');

-- ---------------------------------------------------------
-- user_themes & entity_resonance: AI-derived narrative threads and fit
-- ---------------------------------------------------------
-- Both are model output. Every row says which model and prompt produced it,
-- carries the evidence it was drawn from, and has is_estimated pinned TRUE so no
-- query can pass it off as measured. A theme starts 'suggested' and only the
-- user can accept it.
CREATE TABLE IF NOT EXISTS desk.user_theme (
    id              BIGSERIAL    PRIMARY KEY,
    user_id         BIGINT       NOT NULL REFERENCES warehouse.app_user(id) ON DELETE CASCADE,
    title           VARCHAR(120) NOT NULL,
    summary         VARCHAR(1000) NOT NULL,
    traits          TEXT[]       NOT NULL DEFAULT '{}',
    -- [{"kind": "essay_review" | "task" | "user_note", "refId": "...", "quote": "..."}]
    -- Quotes come from the user's own material. A theme with no evidence is not stored.
    evidence        JSONB        NOT NULL CHECK (jsonb_typeof(evidence) = 'array' AND jsonb_array_length(evidence) > 0),
    status          VARCHAR(10)  NOT NULL DEFAULT 'suggested' CHECK (status IN ('suggested', 'accepted', 'dismissed')),
    model_name      VARCHAR(100) NOT NULL,
    prompt_version  VARCHAR(40)  NOT NULL,
    is_estimated    BOOLEAN      NOT NULL DEFAULT TRUE CHECK (is_estimated),
    generated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    decided_at      TIMESTAMPTZ,
    CONSTRAINT user_theme_id_user_key UNIQUE (id, user_id)
);

CREATE INDEX IF NOT EXISTS user_theme_user_status_idx
    ON desk.user_theme (user_id, status);

CREATE TABLE IF NOT EXISTS desk.entity_resonance (
    id                 BIGSERIAL    PRIMARY KEY,
    user_id            BIGINT       NOT NULL,
    theme_id           BIGINT       NOT NULL,
    target_entity_id   BIGINT       NOT NULL,
    -- A five-step ordinal, not a percentage: the model can say "stronger than"
    -- but has nothing to measure 73 against 71 with. The UI draws five segments.
    level              SMALLINT     NOT NULL CHECK (level BETWEEN 1 AND 5),
    rationale          VARCHAR(1000) NOT NULL,
    -- Where the institution side came from. The warehouse holds ranks and
    -- requirements, not what a school values, so this is either the user's own
    -- notes or the model's general knowledge -- and the API says which.
    -- Wikipedia text is never an input (see CLAUDE.md, "Wikipedia introductions").
    institution_basis  VARCHAR(24)  NOT NULL CHECK (institution_basis IN ('user_notes', 'model_general_knowledge')),
    evidence           JSONB        NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(evidence) = 'array'),
    model_name         VARCHAR(100) NOT NULL,
    prompt_version     VARCHAR(40)  NOT NULL,
    is_estimated       BOOLEAN      NOT NULL DEFAULT TRUE CHECK (is_estimated),
    generated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT entity_resonance_theme_same_user FOREIGN KEY (theme_id, user_id)
        REFERENCES desk.user_theme (id, user_id) ON DELETE CASCADE,
    CONSTRAINT entity_resonance_target_same_user FOREIGN KEY (target_entity_id, user_id)
        REFERENCES desk.target_entity (id, user_id) ON DELETE CASCADE,
    CONSTRAINT entity_resonance_pair_key UNIQUE (theme_id, target_entity_id)
);

-- ---------------------------------------------------------
-- skill_mastery: test / unit mastery
-- ---------------------------------------------------------
-- Mastery is counted, not judged: correct / attempted, computed by the database
-- so no writer can store a percentage that disagrees with its own counts.
CREATE TABLE IF NOT EXISTS desk.skill_mastery (
    id                   BIGSERIAL    PRIMARY KEY,
    user_id              BIGINT       NOT NULL REFERENCES warehouse.app_user(id) ON DELETE CASCADE,
    subject              VARCHAR(60)  NOT NULL,   -- 'SAT Math', 'IELTS Reading'
    unit                 VARCHAR(80)  NOT NULL,   -- 'Algebra', 'Geometry & trig'
    questions_attempted  INTEGER      NOT NULL DEFAULT 0 CHECK (questions_attempted >= 0),
    questions_correct    INTEGER      NOT NULL DEFAULT 0 CHECK (questions_correct >= 0),
    mastery_pct          NUMERIC(4,1) GENERATED ALWAYS AS (
                             CASE WHEN questions_attempted = 0 THEN NULL
                                  ELSE round(100.0 * questions_correct / questions_attempted, 1) END
                         ) STORED,
    source               VARCHAR(16)  NOT NULL DEFAULT 'practice' CHECK (source IN ('practice', 'mock_test', 'self_reported')),
    last_practiced_at    TIMESTAMPTZ,
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT skill_mastery_correct_le_attempted CHECK (questions_correct <= questions_attempted),
    CONSTRAINT skill_mastery_unit_key UNIQUE (user_id, subject, unit)
);

-- ---------------------------------------------------------
-- essay_reviews: scored drafts, dimension scores and suggested edits
-- ---------------------------------------------------------
-- One row per evaluated draft. A redraft is a new row pointing at the one it
-- revises, so the UI can diff two drafts and plot the score across them.
--
-- dimension_scores is model output against a versioned rubric:
--   {"impact": {"score": 82, "rationale": "...", "evidence": [{"start": 120, "end": 188}]}, ...}
-- overall_score is NOT model output: the API computes it from dimension_scores
-- with the rubric's fixed weights, so the headline number is reproducible.
--
-- suggestions are edits anchored to character offsets in draft_text:
--   [{"start": 412, "end": 470, "original": "...", "suggested": "...", "dimension": "introspection", "reason": "..."}]
CREATE TABLE IF NOT EXISTS desk.essay_review (
    id                BIGSERIAL     PRIMARY KEY,
    user_id           BIGINT        NOT NULL REFERENCES warehouse.app_user(id) ON DELETE CASCADE,
    essay_title       VARCHAR(200)  NOT NULL,
    essay_prompt      TEXT,
    target_entity_id  BIGINT,
    revision_of_id    BIGINT,
    draft_text        TEXT          NOT NULL CHECK (length(draft_text) BETWEEN 1 AND 20000),
    word_count        INTEGER       NOT NULL CHECK (word_count >= 0),
    -- sha256 of draft_text: re-evaluating an unchanged draft returns the stored review.
    draft_sha256      CHAR(64)      NOT NULL,
    rubric_version    VARCHAR(40)   NOT NULL,
    dimension_scores  JSONB         NOT NULL CHECK (jsonb_typeof(dimension_scores) = 'object'),
    overall_score     NUMERIC(4,1)  NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
    suggestions       JSONB         NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(suggestions) = 'array'),
    model_name        VARCHAR(100)  NOT NULL,
    is_estimated      BOOLEAN       NOT NULL DEFAULT TRUE CHECK (is_estimated),
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT essay_review_id_user_key UNIQUE (id, user_id),
    CONSTRAINT essay_review_target_same_user FOREIGN KEY (target_entity_id, user_id)
        REFERENCES desk.target_entity (id, user_id) ON DELETE SET NULL (target_entity_id),
    CONSTRAINT essay_review_revision_same_user FOREIGN KEY (revision_of_id, user_id)
        REFERENCES desk.essay_review (id, user_id) ON DELETE SET NULL (revision_of_id),
    CONSTRAINT essay_review_draft_rubric_key UNIQUE (user_id, draft_sha256, rubric_version)
);

CREATE INDEX IF NOT EXISTS essay_review_user_created_idx
    ON desk.essay_review (user_id, created_at DESC);
