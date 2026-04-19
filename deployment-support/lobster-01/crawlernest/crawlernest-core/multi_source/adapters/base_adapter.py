from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable

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
