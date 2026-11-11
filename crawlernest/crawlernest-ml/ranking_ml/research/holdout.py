"""How many times the holdout has been read, across runs.

The loop reads the holdout once per report, so within one run it is clean. Across runs it is not: each rerun that
looks at the holdout and then changes the search is a choice made on the holdout, and after a few of those its
figure is no longer an honest estimate. The ledger counts reads per (snapshot, split) in a file under
``.local/reports/research/`` and the report refuses to read the holdout again past ``max_reads``. The fix is a fresh
holdout -- the next QS edition, or a new split -- not a higher limit.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MAX_READS = 3


def holdout_key(snapshot: Path, split_rule: str) -> str:
    """The holdout's identity: the bytes of the snapshot it comes from, and the rule that cut it."""
    digest = hashlib.sha256(Path(snapshot).read_bytes()).hexdigest()[:16]
    return f"{digest}:{split_rule}"


@dataclass
class HoldoutLedger:
    path: Path
    key: str
    max_reads: int = DEFAULT_MAX_READS

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(Path(self.path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def reads(self) -> int:
        return len(self._load().get(self.key, []))

    def may_read(self) -> bool:
        return self.reads() < self.max_reads

    def record_read(self, note: str = "") -> int:
        data = self._load()
        entries = data.setdefault(self.key, [])
        entries.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "note": note})
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return len(entries)
