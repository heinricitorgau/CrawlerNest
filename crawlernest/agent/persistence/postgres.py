from __future__ import annotations

"""A connection pool per database URL, shared by every store in the process.

Created lazily, on first use, so each worker process builds its own after it
starts: a psycopg2 connection inherited across fork is shared by two processes
and corrupts both sessions.
"""

import os
import threading
from contextlib import contextmanager
from typing import Any, Iterator

POOL_MAX_ENV = "CRAWLERNEST_AGENT_DB_POOL_MAX"

REQUIRED_TABLES = (
    "long_term_memory",
    "strategy",
    "experience",
    "patch",
    "conversation_turn",
)


class AgentStateSchemaMissing(RuntimeError):
    """The agent_state tables are not there; the API refuses to start without them."""


class ConnectionPool:
    """psycopg2's ThreadedConnectionPool, made to wait instead of fail.

    ThreadedConnectionPool raises PoolError the moment every connection is out.
    Request handlers run in a thread pool larger than any sensible connection
    count, so a burst would turn into errors. The semaphore makes the extra
    threads wait for a connection instead.
    """

    def __init__(self, dsn: str, *, max_connections: int | None = None) -> None:
        from psycopg2.pool import ThreadedConnectionPool

        size = max_connections or int(os.environ.get(POOL_MAX_ENV, "10"))
        self._pool = ThreadedConnectionPool(minconn=1, maxconn=size, dsn=dsn)
        self._slots = threading.BoundedSemaphore(size)
        self.dsn = dsn

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """A cursor inside one transaction: committed on exit, rolled back on error."""
        import psycopg2

        self._slots.acquire()
        conn = self._pool.getconn()
        broken = False
        try:
            try:
                with conn:
                    with conn.cursor() as cur:
                        yield cur
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                broken = True
                raise
        finally:
            self._pool.putconn(conn, close=broken or bool(conn.closed))
            self._slots.release()

    def verify_schema(self) -> None:
        with self.transaction() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'agent_state'
                """
            )
            present = {row[0] for row in cur.fetchall()}
        missing = [name for name in REQUIRED_TABLES if name not in present]
        if missing:
            raise AgentStateSchemaMissing(
                "agent_state is missing " + ", ".join(missing) + ". Apply "
                "crawlernest/crawlernest-schema/agent_state_postgresql.sql "
                "(python3 -m crawlernest.run_pipeline bootstrap-postgres does) before starting "
                "the agent API with CRAWLERNEST_AGENT_STORE_BACKEND=postgres."
            )

    def ping(self) -> None:
        with self.transaction() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()

    def close(self) -> None:
        self._pool.closeall()


_pools: dict[str, ConnectionPool] = {}
_pools_lock = threading.Lock()


def connection_pool(dsn: str) -> ConnectionPool:
    with _pools_lock:
        pool = _pools.get(dsn)
        if pool is None:
            pool = ConnectionPool(dsn)
            _pools[dsn] = pool
        return pool


def close_all_pools() -> None:
    with _pools_lock:
        for pool in _pools.values():
            pool.close()
        _pools.clear()
