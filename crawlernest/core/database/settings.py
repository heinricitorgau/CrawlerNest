from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    host: str = "127.0.0.1"
    port: int = 5432
    database: str = "clawer"
    user: str = "test"
    password: str = "test"

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        return cls(
            host=os.getenv("CRAWLERNEST_PG_HOST", "127.0.0.1"),
            port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            database=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            user=os.getenv("CRAWLERNEST_PG_USER", "test"),
            password=os.getenv("CRAWLERNEST_PG_PASSWORD", "test"),
        )
