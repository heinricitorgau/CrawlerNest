from __future__ import annotations

from typing import Any

from crawlernest.core.database.settings import DatabaseSettings
from crawlernest.core.services.rank_history import load_rank_history
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
        data = detail_preview_to_dict(preview)
        data["rank_history"] = self._rank_history(data.get("canonical_university_id"))
        # The lookup explainer reads "caveats". The admission caveats sat under admission_caveats alone and never
        # reached it; the rank history's join them, deduplicated, order kept.
        history_caveats = (data["rank_history"] or {}).get("caveats") or []
        data["caveats"] = list(dict.fromkeys([*(data.get("admission_caveats") or []), *history_caveats]))
        return data

    def _rank_history(self, canonical_university_id: Any) -> dict[str, Any] | None:
        """Every held edition per source, or None when it cannot be read (the lookup still answers)."""
        if canonical_university_id is None:
            return None
        try:
            import psycopg2

            conn = psycopg2.connect(
                host=self._db_settings.host,
                port=self._db_settings.port,
                dbname=self._db_settings.database,
                user=self._db_settings.user,
                password=self._db_settings.password,
            )
        except Exception:
            return None
        try:
            return load_rank_history(conn, int(canonical_university_id))
        except Exception:
            return None
        finally:
            conn.close()

