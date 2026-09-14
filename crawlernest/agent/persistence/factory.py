from __future__ import annotations

"""Choose each agent store's backend from the environment.

Imports of the store classes are deferred to the functions: the JSON stores
import nothing from here at module level, and keeping it that way means this
module can be imported by any of them without a cycle.
"""

import os
from pathlib import Path
from typing import Any

BACKEND_ENV = "CRAWLERNEST_AGENT_STORE_BACKEND"
STATE_DIR_ENV = "CRAWLERNEST_AGENT_STATE_DIR"
DATABASE_URL_ENV = "CRAWLERNEST_AGENT_DATABASE_URL"

JSON = "json"
POSTGRES = "postgres"
BACKENDS = (JSON, POSTGRES)


class AgentStoreConfigError(RuntimeError):
    """The environment asks for a store backend it does not configure."""


def store_backend() -> str:
    value = (os.environ.get(BACKEND_ENV) or JSON).strip().lower()
    if value not in BACKENDS:
        raise AgentStoreConfigError(
            f"{BACKEND_ENV}={value!r} is not a store backend; use one of {', '.join(BACKENDS)}."
        )
    return value


def state_dir() -> Path:
    """Directory for the JSON backend's files.

    ``CRAWLERNEST_AGENT_STATE_DIR``, else ``$XDG_STATE_HOME/crawlernest/agent``,
    else ``~/.local/state/crawlernest/agent``. Deliberately not ``/tmp``: that is
    where the stores used to live, and a reboot emptied them without a trace.
    """
    explicit = os.environ.get(STATE_DIR_ENV)
    if explicit:
        return Path(explicit).expanduser()
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base).expanduser() / "crawlernest" / "agent"


def json_store_path(explicit: str | None, env_var: str, filename: str) -> Path:
    """An explicit path, then the store's own env override, then the state dir."""
    return Path(explicit or os.environ.get(env_var) or state_dir() / filename)


def database_url() -> str:
    url = (os.environ.get(DATABASE_URL_ENV) or "").strip()
    if not url:
        raise AgentStoreConfigError(
            f"{BACKEND_ENV}=postgres needs {DATABASE_URL_ENV}, e.g. "
            "postgresql://agent@localhost:5432/clawer. Keep the password out of the URL: "
            "libpq reads PGPASSWORD or ~/.pgpass."
        )
    return url


def state_pool() -> Any:
    from crawlernest.agent.persistence.postgres import connection_pool

    return connection_pool(database_url())


def long_term_memory_store() -> Any:
    if store_backend() == POSTGRES:
        from crawlernest.agent.persistence.postgres_stores import PostgresLongTermMemoryStore

        return PostgresLongTermMemoryStore(state_pool())
    from crawlernest.agent.memory_long_term.memory_store import LongTermMemoryStore

    return LongTermMemoryStore()


def strategy_store() -> Any:
    if store_backend() == POSTGRES:
        from crawlernest.agent.persistence.postgres_stores import PostgresStrategyStore

        return PostgresStrategyStore(state_pool())
    from crawlernest.agent.self_improvement.strategy_store import StrategyStore

    return StrategyStore()


def experience_store() -> Any:
    if store_backend() == POSTGRES:
        from crawlernest.agent.persistence.postgres_stores import PostgresExperienceStore

        return PostgresExperienceStore(state_pool())
    from crawlernest.agent.self_improvement.experience_store import ExperienceStore

    return ExperienceStore()


def patch_store() -> Any:
    if store_backend() == POSTGRES:
        from crawlernest.agent.persistence.postgres_stores import PostgresPatchStore

        return PostgresPatchStore(state_pool())
    from crawlernest.agent.self_rewrite.patch_store import PatchStore

    return PatchStore()


def conversation_store() -> Any:
    if store_backend() == POSTGRES:
        from crawlernest.agent.persistence.postgres_stores import PostgresConversationStore

        return PostgresConversationStore(state_pool())
    from crawlernest.agent.web_agent.memory.conversation_store import ConversationStore

    return ConversationStore()
