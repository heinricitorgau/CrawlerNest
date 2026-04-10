from __future__ import annotations


class Memory:
    def __init__(self, limit: int = 5) -> None:
        self.limit = limit
        self._items: list[dict[str, str]] = []

    def add(self, task: str, result: str) -> None:
        self._items.append({"task": task, "result": result})
        if len(self._items) > self.limit:
            self._items = self._items[-self.limit :]

    def get_context(self) -> list[dict[str, str]]:
        return list(self._items)

