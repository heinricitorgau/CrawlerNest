from __future__ import annotations

"""PostgreSQL implementations of the agent stores.

Each class keeps the public methods, arguments and return shapes of the JSON
store it replaces, and shares that store's pure logic (filtering, ordering,
record construction) rather than re-deriving it. What changes is where state
lives and who can race on it:

* nothing is cached in the process, so every worker reads the same rows;
* read-modify-write happens inside one transaction, under a row lock or a
  unique constraint, so concurrent writers cannot lose each other's updates.

Schema: crawlernest-schema/agent_state_postgresql.sql.
"""

import hashlib
import json
import time
import uuid
from typing import Any

from psycopg2.extras import Json

from crawlernest.agent.memory_long_term.memory_store import decay_score_for, rank_memories
from crawlernest.agent.memory_long_term.memory_types import MemoryEntry
from crawlernest.agent.persistence.postgres import ConnectionPool
from crawlernest.agent.self_improvement.experience_store import build_experience
from crawlernest.agent.self_improvement.strategy_store import (
    apply_strategy_update,
    normalize_target,
    rollout_allows,
    select_strategies,
)
from crawlernest.agent.self_rewrite.patch_store import build_patch_record
from crawlernest.agent.web_agent.memory.conversation_store import ConversationTurn


def _json(value: Any) -> Json:
    return Json(value, dumps=lambda obj: json.dumps(obj, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Long-term memory
# ---------------------------------------------------------------------------


class PostgresLongTermMemoryStore:
    def __init__(self, pool: ConnectionPool, *, max_entries_per_user: int = 200) -> None:
        self._pool = pool
        self._max_entries_per_user = max_entries_per_user

    def insert(
        self,
        *,
        memory_type: str,
        content: str,
        metadata: dict,
        importance: float,
    ) -> MemoryEntry:
        user_id = str(metadata.get("user_id") or "").strip()
        stamped = {**metadata, "timestamp": time.time()}
        entities = sorted(
            {str(e).strip().lower() for e in (metadata.get("entities") or []) if str(e).strip()}
        )
        with self._pool.transaction() as cur:
            # A repeat of the same (user, type, content) merges into the row
            # already there, as the JSON store did: metadata keys overwrite,
            # importance only rises, and the timestamp resets the decay.
            cur.execute(
                """
                INSERT INTO agent_state.long_term_memory (
                    memory_id, user_id, memory_type, content, content_hash,
                    entities, metadata, importance
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, memory_type, content_hash) DO UPDATE SET
                    metadata = agent_state.long_term_memory.metadata || EXCLUDED.metadata,
                    entities = CASE WHEN EXCLUDED.metadata ? 'entities'
                                    THEN EXCLUDED.entities
                                    ELSE agent_state.long_term_memory.entities END,
                    importance = GREATEST(agent_state.long_term_memory.importance, EXCLUDED.importance),
                    updated_at = CURRENT_TIMESTAMP
                RETURNING memory_id, memory_type, content, metadata, importance
                """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    memory_type,
                    content,
                    hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    entities,
                    _json(stamped),
                    max(0.0, min(1.0, float(importance))),
                ),
            )
            memory_id, stored_type, stored_content, stored_metadata, stored_importance = cur.fetchone()
            if user_id:
                cur.execute(
                    """
                    DELETE FROM agent_state.long_term_memory
                    WHERE memory_id IN (
                        SELECT memory_id FROM agent_state.long_term_memory
                        WHERE user_id = %s
                        ORDER BY updated_at DESC, memory_id
                        OFFSET %s
                    )
                    """,
                    (user_id, self._max_entries_per_user),
                )
        return MemoryEntry(
            id=str(memory_id),
            type=stored_type,
            content=stored_content,
            metadata=dict(stored_metadata or {}),
            importance=float(stored_importance),
            decay_score=0.0,
        )

    def query(
        self,
        *,
        user_id: str | None,
        entities: list[str] | None = None,
        types: list[str] | None = None,
        limit: int = 8,
    ) -> list[MemoryEntry]:
        with self._pool.transaction() as cur:
            rows = self._lookup(cur, user_id=user_id, entities=entities, types=types)
            if not rows and user_id:
                rows = self._lookup(cur, user_id=user_id, entities=None, types=types)
        now = time.time()
        entries = [
            MemoryEntry(
                id=str(memory_id),
                type=memory_type,
                content=content,
                metadata=dict(metadata or {}),
                importance=float(importance),
                decay_score=decay_score_for(float((metadata or {}).get("timestamp", now)), now),
            )
            for memory_id, memory_type, content, metadata, importance in rows
        ]
        return rank_memories(entries, limit)

    def decay(self) -> None:
        """Decay is derived from each row's timestamp when read; nothing to store."""
        return None

    @staticmethod
    def _lookup(
        cur: Any,
        *,
        user_id: str | None,
        entities: list[str] | None,
        types: list[str] | None,
    ) -> list[tuple]:
        """MemoryIndex.lookup, as SQL.

        The index intersects a user set, an entity set and a type set, but an
        entity or type filter with no match anywhere is dropped rather than
        emptying the result. That "anywhere" is the whole table, not this
        user's rows, so it is checked on its own.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if user_id:
            clauses.append("user_id = %s")
            params.append(user_id)
        entity_keys = sorted({str(e).strip().lower() for e in (entities or []) if str(e).strip()})
        if entity_keys:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM agent_state.long_term_memory WHERE entities && %s)",
                (entity_keys,),
            )
            if cur.fetchone()[0]:
                clauses.append("entities && %s")
                params.append(entity_keys)
        type_keys = [str(t) for t in (types or [])]
        if type_keys:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM agent_state.long_term_memory WHERE memory_type = ANY(%s))",
                (type_keys,),
            )
            if cur.fetchone()[0]:
                clauses.append("memory_type = ANY(%s)")
                params.append(type_keys)
        if not clauses:
            return []
        cur.execute(
            "SELECT memory_id, memory_type, content, metadata, importance "
            "FROM agent_state.long_term_memory WHERE " + " AND ".join(clauses),
            params,
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


class PostgresStrategyStore:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def upsert(
        self,
        *,
        engine: str,
        task_kind: str,
        strategy: list[str],
        confidence: float,
        reason: str,
        target: str | None = None,
        strategy_type: str = "behavior",
        source: str = "experience_analysis",
        rollout_percent: int = 100,
        status: str = "active",
    ) -> dict[str, Any]:
        normalized = normalize_target(target)
        fresh = {
            "id": str(uuid.uuid4()),
            "created_at": time.time(),
            "engine": engine,
            "task_kind": task_kind,
            "target": normalized,
            "strategy_type": strategy_type,
            "version": "v1",
            "previous": None,
        }
        with self._pool.transaction() as cur:
            # Insert-or-nothing, then lock whichever row holds the key. Two
            # workers upserting one key both reach the same row, one after the
            # other, instead of each creating its own.
            cur.execute(
                """
                INSERT INTO agent_state.strategy (strategy_id, engine, task_kind, target, strategy_type, document)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (fresh["id"], engine, task_kind, normalized, strategy_type, _json(fresh)),
            )
            cur.execute(
                """
                SELECT strategy_id, document FROM agent_state.strategy
                WHERE engine = %s AND task_kind = %s AND COALESCE(target, '') = COALESCE(%s, '')
                  AND strategy_type = %s
                FOR UPDATE
                """,
                (engine, task_kind, normalized, strategy_type),
            )
            strategy_id, document = cur.fetchone()
            entry = apply_strategy_update(
                dict(document),
                strategy=strategy,
                confidence=confidence,
                reason=reason,
                source=source,
                rollout_percent=rollout_percent,
                status=status,
            )
            cur.execute(
                "UPDATE agent_state.strategy SET document = %s, updated_at = CURRENT_TIMESTAMP WHERE strategy_id = %s",
                (_json(entry), strategy_id),
            )
        return dict(entry)

    def query(
        self,
        *,
        engine: str,
        task_kind: str,
        target: str | None = None,
        min_confidence: float = 0.55,
        limit: int = 3,
        strategy_type: str | None = None,
        require_active: bool = True,
    ) -> list[dict[str, Any]]:
        with self._pool.transaction() as cur:
            cur.execute(
                "SELECT document FROM agent_state.strategy WHERE engine = %s AND task_kind = %s",
                (engine, task_kind),
            )
            items = [dict(row[0]) for row in cur.fetchall()]
        return select_strategies(
            items,
            engine=engine,
            task_kind=task_kind,
            target=target,
            min_confidence=min_confidence,
            limit=limit,
            strategy_type=strategy_type,
            require_active=require_active,
        )

    def record_outcome(self, *, strategy_id: str, success: bool) -> dict[str, Any] | None:
        key = "success_count" if success else "failure_count"
        with self._pool.transaction() as cur:
            cur.execute(
                """
                UPDATE agent_state.strategy
                SET document = jsonb_set(
                        document, %s,
                        to_jsonb(COALESCE((document ->> %s)::int, 0) + 1)
                    ),
                    updated_at = CURRENT_TIMESTAMP
                WHERE document ->> 'id' = %s
                RETURNING document
                """,
                ([key], key, strategy_id),
            )
            row = cur.fetchone()
        return dict(row[0]) if row else None

    def rollback(self, *, strategy_id: str, reason: str) -> dict[str, Any] | None:
        with self._pool.transaction() as cur:
            cur.execute(
                """
                UPDATE agent_state.strategy
                SET document = document || %s, updated_at = CURRENT_TIMESTAMP
                WHERE document ->> 'id' = %s
                RETURNING document
                """,
                (
                    _json({"status": "rolled_back", "rollback_reason": reason, "updated_at": time.time()}),
                    strategy_id,
                ),
            )
            row = cur.fetchone()
        return dict(row[0]) if row else None

    def rollout_allows(self, *, entry: dict[str, Any], request_signature: str) -> bool:
        return rollout_allows(entry=entry, request_signature=request_signature)


# ---------------------------------------------------------------------------
# Experiences and patches
# ---------------------------------------------------------------------------


class PostgresExperienceStore:
    def __init__(self, pool: ConnectionPool, *, max_entries: int = 2000) -> None:
        self._pool = pool
        self._max_entries = max_entries

    def append(
        self,
        *,
        engine: str,
        task_kind: str,
        task: str,
        status: str,
        final_score: float,
        tools_used: list[str],
        steps: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = build_experience(
            engine=engine,
            task_kind=task_kind,
            task=task,
            status=status,
            final_score=final_score,
            tools_used=tools_used,
            steps=steps,
            metadata=metadata,
        )
        with self._pool.transaction() as cur:
            cur.execute(
                "INSERT INTO agent_state.experience (experience_id, engine, task_kind, document) VALUES (%s, %s, %s, %s)",
                (entry["id"], engine, task_kind, _json(entry)),
            )
            cur.execute(
                """
                DELETE FROM agent_state.experience
                WHERE seq <= (
                    SELECT seq FROM agent_state.experience ORDER BY seq DESC OFFSET %s LIMIT 1
                )
                """,
                (self._max_entries,),
            )
        return dict(entry)

    def recent(
        self,
        *,
        engine: str | None = None,
        task_kind: str | None = None,
        target: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if engine:
            clauses.append("engine = %s")
            params.append(engine)
        if task_kind:
            clauses.append("task_kind = %s")
            params.append(task_kind)
        if target:
            clauses.append("lower(document -> 'metadata' ->> 'target') = lower(%s)")
            params.append(target)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._pool.transaction() as cur:
            cur.execute(
                f"SELECT document FROM agent_state.experience {where} ORDER BY seq DESC LIMIT %s",
                [*params, limit],
            )
            return [dict(row[0]) for row in cur.fetchall()]


class PostgresPatchStore:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def append(
        self,
        *,
        task: str,
        patch_candidate: dict[str, Any],
        patch_validation: dict[str, Any],
        patch_execution: dict[str, Any],
    ) -> dict[str, Any]:
        entry = build_patch_record(
            task=task,
            patch_candidate=patch_candidate,
            patch_validation=patch_validation,
            patch_execution=patch_execution,
        )
        with self._pool.transaction() as cur:
            cur.execute(
                "INSERT INTO agent_state.patch (patch_id, status, document) VALUES (%s, %s, %s)",
                (entry["id"], entry["status"], _json(entry)),
            )
        return dict(entry)


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------


class PostgresConversationStore:
    def __init__(
        self,
        pool: ConnectionPool,
        *,
        max_turns_per_session: int = 20,
        max_sessions: int = 500,
    ) -> None:
        self._pool = pool
        self._max_turns = max_turns_per_session
        self._max_sessions = max_sessions

    def get_history(self, session_id: str) -> list[ConversationTurn]:
        with self._pool.transaction() as cur:
            cur.execute(
                """
                SELECT role, content, task_kind, metadata FROM (
                    SELECT turn_id, role, content, task_kind, metadata
                    FROM agent_state.conversation_turn
                    WHERE session_id = %s
                    ORDER BY turn_id DESC
                    LIMIT %s
                ) recent
                ORDER BY turn_id
                """,
                (session_id, self._max_turns),
            )
            return [
                ConversationTurn(role=role, content=content, task_kind=task_kind, metadata=dict(metadata or {}))
                for role, content, task_kind, metadata in cur.fetchall()
            ]

    def append_user(self, session_id: str, *, content: str, task_kind: str = "") -> None:
        self._append(session_id, role="user", content=content, task_kind=task_kind)

    def append_assistant(self, session_id: str, *, content: str, task_kind: str = "") -> None:
        self._append(session_id, role="assistant", content=content, task_kind=task_kind)

    def clear_session(self, session_id: str) -> None:
        with self._pool.transaction() as cur:
            cur.execute("DELETE FROM agent_state.conversation_turn WHERE session_id = %s", (session_id,))

    def session_count(self) -> int:
        with self._pool.transaction() as cur:
            cur.execute("SELECT count(DISTINCT session_id) FROM agent_state.conversation_turn")
            return int(cur.fetchone()[0])

    def _append(self, session_id: str, *, role: str, content: str, task_kind: str) -> None:
        with self._pool.transaction() as cur:
            cur.execute(
                """
                INSERT INTO agent_state.conversation_turn (session_id, role, content, task_kind)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, role, content, task_kind),
            )
            # Keep this session's newest turns.
            cur.execute(
                """
                DELETE FROM agent_state.conversation_turn
                WHERE session_id = %s
                  AND turn_id <= (
                      SELECT turn_id FROM agent_state.conversation_turn
                      WHERE session_id = %s ORDER BY turn_id DESC OFFSET %s LIMIT 1
                  )
                """,
                (session_id, session_id, self._max_turns),
            )
            # Evict the least recently active sessions past the cap -- the LRU
            # the in-memory store kept, measured by each session's newest turn.
            cur.execute(
                """
                DELETE FROM agent_state.conversation_turn
                WHERE session_id IN (
                    SELECT session_id FROM agent_state.conversation_turn
                    GROUP BY session_id
                    ORDER BY max(turn_id) DESC
                    OFFSET %s
                )
                """,
                (self._max_sessions,),
            )
