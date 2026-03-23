from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable

from ..types import StandardizedRankingRecord


class BaseSourceAdapter(ABC):
    source_code: str

    @abstractmethod
    def adapt(self, payload: Iterable[Any]) -> list[StandardizedRankingRecord]:
        raise NotImplementedError
