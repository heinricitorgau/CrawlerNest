from __future__ import annotations


class Logger:
    @staticmethod
    def info(message: str) -> None:
        print(f"[INFO] {message}")
