"""Where the agent API keeps state that must outlive a request.

Two backends, chosen by ``CRAWLERNEST_AGENT_STORE_BACKEND``:

``json`` (default)
    One JSON file per store under the agent state directory, written
    atomically. For a single local process. It used to default to ``/tmp``,
    which a reboot empties.

``postgres``
    The ``agent_state`` schema (crawlernest-schema/agent_state_postgresql.sql),
    reached through ``CRAWLERNEST_AGENT_DATABASE_URL``. Required for more than one
    worker: JSON files rewritten whole by several processes lose updates, and an
    in-memory conversation history is private to the worker that holds it.

Every engine obtains its stores from :mod:`crawlernest.agent.persistence.factory`
rather than constructing them, so the backend is decided in one place.
"""

from crawlernest.agent.persistence.factory import (
    AgentStoreConfigError,
    conversation_store,
    experience_store,
    long_term_memory_store,
    patch_store,
    state_dir,
    store_backend,
    strategy_store,
)

__all__ = [
    "AgentStoreConfigError",
    "conversation_store",
    "experience_store",
    "long_term_memory_store",
    "patch_store",
    "state_dir",
    "store_backend",
    "strategy_store",
]
