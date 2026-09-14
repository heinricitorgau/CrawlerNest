-- =========================================================
-- Agent API runtime state
-- =========================================================
--
-- The agent API used to keep five stores in process memory and in whole-file
-- JSON under /tmp: long-term memory, dev-agent strategies, experiences and
-- patch records, plus conversation history held only in memory. That was
-- acceptable for one dev process and wrong for a service:
--
--   * /tmp is cleared on reboot, so memory and strategies silently vanished;
--   * every write rewrote the whole file, so two worker processes lost each
--     other's updates, and a crash mid-write left a truncated file that the
--     loader then discarded without a word;
--   * each worker had its own conversation history, so a follow-up question
--     answered by a different worker lost its referent.
--
-- These tables are what CRAWLERNEST_AGENT_STORE_BACKEND=postgres reads and
-- writes (crawlernest/agent/persistence/). The agent API owns this schema and
-- nothing else writes it. It holds no ranking data and nothing here is read by
-- the Spring Boot API, so it lives apart from warehouse and analytics.
--
-- None of it is derived from the warehouse: losing it loses agent history, not
-- published data.

CREATE SCHEMA IF NOT EXISTS agent_state;

-- ---------------------------------------------------------
-- Long-term memory (LongTermMemoryStore)
-- ---------------------------------------------------------
-- One row per (user, type, content). A repeat insert merges metadata and keeps
-- the higher importance, which is what the JSON store did by scanning.
-- content_hash, not content, carries the uniqueness: a btree entry is capped
-- near 2.7 kB and memory content has no length limit.
CREATE TABLE IF NOT EXISTS agent_state.long_term_memory (
    memory_id UUID PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT '',
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    -- Lower-cased copy of metadata.entities, so lookup can use the GIN index.
    entities TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    importance DOUBLE PRECISION NOT NULL CHECK (importance >= 0 AND importance <= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_long_term_memory_content UNIQUE (user_id, memory_type, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_long_term_memory_user
    ON agent_state.long_term_memory (user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_long_term_memory_entities
    ON agent_state.long_term_memory USING GIN (entities);

-- ---------------------------------------------------------
-- Dev-agent strategies (StrategyStore)
-- ---------------------------------------------------------
-- The JSON store kept one entry per (engine, task_kind, target, strategy_type)
-- and updated it in place. The unique index makes that a database guarantee, so
-- two workers upserting the same key produce one row rather than two.
-- document is the exact dict the store returns.
CREATE TABLE IF NOT EXISTS agent_state.strategy (
    strategy_id UUID PRIMARY KEY,
    engine TEXT NOT NULL,
    task_kind TEXT NOT NULL,
    target TEXT,
    strategy_type TEXT NOT NULL,
    document JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_strategy_key
    ON agent_state.strategy (engine, task_kind, (COALESCE(target, '')), strategy_type);

-- ---------------------------------------------------------
-- Dev-agent experiences (ExperienceStore) and patches (PatchStore)
-- ---------------------------------------------------------
-- Append-only. seq orders rows by insertion, which timestamps cannot do when
-- two land in the same microsecond.
CREATE TABLE IF NOT EXISTS agent_state.experience (
    seq BIGSERIAL PRIMARY KEY,
    experience_id UUID NOT NULL UNIQUE,
    engine TEXT NOT NULL,
    task_kind TEXT NOT NULL,
    document JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_experience_engine_kind
    ON agent_state.experience (engine, task_kind, seq DESC);

CREATE TABLE IF NOT EXISTS agent_state.patch (
    seq BIGSERIAL PRIMARY KEY,
    patch_id UUID NOT NULL UNIQUE,
    status TEXT NOT NULL,
    document JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- Conversation history (ConversationStore)
-- ---------------------------------------------------------
-- Shared by every worker, so a follow-up reaches the turns before it whichever
-- process answers. Capped per session and by session count, as in memory.
CREATE TABLE IF NOT EXISTS agent_state.conversation_turn (
    turn_id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    task_kind TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversation_turn_session
    ON agent_state.conversation_turn (session_id, turn_id DESC);
