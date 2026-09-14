from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_json_atomically(path: Path, payload: Any) -> None:
    """Replace *path* with *payload* so a reader sees the old file or the new one.

    The stores used to ``write_text`` in place. A process killed mid-write left
    a truncated file, and every loader treats an unparseable file as empty, so
    the next start silently discarded all of it. Writing a sibling temp file and
    renaming it over the target is atomic on POSIX filesystems.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
