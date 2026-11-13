"""docs/README.md lists every document under docs/, and every link in it resolves.

The hub had fallen 52 documents behind the folder (and listed seven twice) before this test existed. It reads
only the git-tracked files, so a local-only file such as the gitignored COMMIT_LOG.md is not required.
"""
from __future__ import annotations

import posixpath
import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HUB = REPO_ROOT / "docs" / "README.md"
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def _tracked_docs() -> list[str]:
    out = subprocess.run(["git", "ls-files", "docs"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line]


def _hub_targets() -> list[str]:
    text = HUB.read_text(encoding="utf-8")
    return [posixpath.normpath(posixpath.join("docs", m.group(1))) for m in LINK.finditer(text)
            if not m.group(1).startswith(("http://", "https://", "mailto:"))]


class TestDocsCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.tracked = _tracked_docs()
        except (OSError, subprocess.CalledProcessError) as exc:  # not a git checkout (an sdist, a copy)
            raise unittest.SkipTest(f"git ls-files unavailable: {exc}")
        cls.targets = _hub_targets()

    def test_every_doc_is_listed(self) -> None:
        # Files inside a release are frozen bundle contents; the catalog links each release, not each file.
        docs = [f for f in self.tracked if f.endswith(".md") and not f.startswith("docs/releases/")
                and f != "docs/README.md"]
        missing = sorted(set(docs) - set(self.targets))
        self.assertEqual(missing, [], "add a row to docs/README.md for each of these")

    def test_every_release_is_listed(self) -> None:
        releases = {f.split("/")[2] for f in self.tracked if f.startswith("docs/releases/") and f.count("/") >= 3}
        listed = {t.split("/")[2] for t in self.targets if t.startswith("docs/releases/")}
        self.assertEqual(sorted(releases - listed), [])

    def test_every_link_resolves(self) -> None:
        broken = sorted({t for t in self.targets if not (REPO_ROOT / t).exists()})
        self.assertEqual(broken, [])

    def test_no_doc_has_two_catalog_rows(self) -> None:
        # Start Here and the prose link to docs that also have a row; only a second ROW is a slip.
        rows = [posixpath.normpath(posixpath.join("docs", m.group(1)))
                for line in HUB.read_text(encoding="utf-8").splitlines() if line.startswith("| [")
                for m in [LINK.search(line)] if m]
        self.assertEqual(sorted({r for r in rows if rows.count(r) > 1}), [])


if __name__ == "__main__":
    unittest.main()
