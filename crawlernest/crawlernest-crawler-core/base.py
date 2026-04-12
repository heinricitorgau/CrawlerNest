"""Base crawler primitives shared by ranking and admission engines."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from http_client import HttpClient
from logger import get_logger


class BaseCrawler:
    """Thin shared base class with logging and snapshot helpers."""

    def __init__(
        self,
        *,
        name: str,
        http_client: HttpClient | None = None,
        snapshot_dir: str | Path | None = None,
    ) -> None:
        self.name = name
        self.logger = get_logger(name)
        self.http_client = http_client or HttpClient()
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else None

    def fetch_text(self, url: str) -> str:
        self.logger.info("Fetching %s", url)
        return self.http_client.get_text(url)

    def fetch_json(self, url: str) -> Any:
        self.logger.info("Fetching JSON %s", url)
        return self.http_client.get_json(url)

    def load_snapshot(self, snapshot_name: str) -> str | None:
        if self.snapshot_dir is None:
            return None
        path = self.snapshot_dir / snapshot_name
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def save_snapshot(self, snapshot_name: str, payload: str) -> Path | None:
        if self.snapshot_dir is None:
            return None
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshot_dir / snapshot_name
        path.write_text(payload, encoding="utf-8")
        return path
