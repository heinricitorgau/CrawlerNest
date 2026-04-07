from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

try:
    from psycopg2.pool import SimpleConnectionPool
except ImportError:
    SimpleConnectionPool = None  # type: ignore


class PostgresPool:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "clawer",
        user: str = "test",
        password: str = "",
        minconn: int = 1,
        maxconn: int = 8,
    ):
        if SimpleConnectionPool is None:
            raise RuntimeError("psycopg2 is required for PostgreSQL pooling")
        self._pool = SimpleConnectionPool(
            minconn,
            maxconn,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )

    @contextmanager
    def connection(self) -> Iterator[object]:
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def close(self) -> None:
        self._pool.closeall()
