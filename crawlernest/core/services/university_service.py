from __future__ import annotations

from typing import Any

from crawlernest.core.database.settings import DatabaseSettings
from crawlernest.pipeline.canonical_university_detail_preview import (
    build_canonical_university_detail_preview,
    detail_preview_to_dict,
)


class UniversityService:
    def __init__(self, db_settings: DatabaseSettings | None = None) -> None:
        self._db_settings = db_settings or DatabaseSettings.from_env()

    def get_detail_preview(
        self,
        *,
        canonical_university_id: int | None = None,
        university_name: str | None = None,
    ) -> dict[str, Any]:
        preview = build_canonical_university_detail_preview(
            pg_host=self._db_settings.host,
            pg_port=self._db_settings.port,
            pg_database=self._db_settings.database,
            pg_user=self._db_settings.user,
            pg_password=self._db_settings.password,
            canonical_university_id=canonical_university_id,
            university_name=university_name,
        )
        return detail_preview_to_dict(preview)

