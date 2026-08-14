"""Writing pipeline artifacts to disk.

Lives here rather than in run_pipeline.py because both run_pipeline and the
extracted command modules write artifacts. Keeping it in the entry point would
have forced the command modules to import their own caller.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_json_artifact(path: Path, payload: Any) -> None:
    """Write *payload* as indented UTF-8 JSON, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
