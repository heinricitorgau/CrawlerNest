from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable

# crawlernest-core, alongside this package on sys.path.
from text_hygiene import CleanedText, clean_source_text

from ..types import StandardizedRankingRecord


class BaseSourceAdapter(ABC):
    source_code: str

    @abstractmethod
    def adapt(self, payload: Iterable[Any]) -> list[StandardizedRankingRecord]:
        raise NotImplementedError

    def _to_optional_str(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _clean_name(self, value: Any) -> CleanedText:
        """A name as it should be stored, and what was wrong with what arrived.

        The door every source name comes through, which is why it is here and
        not in each adapter. Ids and URLs deliberately do not use it: an id is a
        key, and silently improving one re-keys a mapping.
        """
        return clean_source_text(self._to_optional_str(value))

    @staticmethod
    def _hygiene_metadata(*cleaned: CleanedText) -> dict[str, Any]:
        """The audit line for a row whose text had to be corrected.

        Empty for almost every row, so it adds nothing to the common case; when
        it is not empty it records that the source sent something a name cannot
        contain, which is a fact about the crawl rather than the university.
        """
        changes = [change for item in cleaned for change in item.changes]
        return {"name_hygiene": changes} if changes else {}

    def _safe_int(self, value: Any) -> int | None:
        try:
            text = self._to_optional_str(value)
            if text is None:
                return None
            return int(float(text.replace(",", "")))
        except Exception:
            return None

    def _safe_float(self, value: Any) -> float | None:
        try:
            text = self._to_optional_str(value)
            if text is None:
                return None
            return float(text.replace(",", ""))
        except Exception:
            return None
