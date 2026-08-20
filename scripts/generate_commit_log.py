#!/usr/bin/env python3
"""Regenerate docs/COMMIT_LOG.md from git history.

    python3 scripts/generate_commit_log.py          # rewrite the doc
    python3 scripts/generate_commit_log.py --check  # fail if it is out of date

The document existed before this script did: it was produced by hand from the
command in its own "重現指令" section, which meant it went stale the moment
anything was committed after it. This reproduces that command's output in the
same format, so bringing the log current is one command rather than an exercise
in careful copying.

The format is fixed by the committed document, not chosen here. Regenerating an
unchanged repository must reproduce the existing rows byte for byte -- that is
the test, and `--check` is how CI can assert it.

## The one commit that can never be listed

Updating the log is itself a commit, so the file can never describe the change
that writes it. The log is therefore current as of its parent. `--check` accounts
for this: it compares against HEAD and reports the gap, so the fix is to run the
generator and amend, or to accept a one-commit lag.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "COMMIT_LOG.md"

#: U+2014 for a statistic a merge commit does not report, U+2212 for a minus
#: sign. Both are what the committed document already uses; ASCII substitutes
#: would show up as a diff on every row.
EM_DASH = "—"
MINUS = "−"

#: RS between commits, US between fields. A single separator for both would
#: shred each record, since every commit carries four internal field breaks.
RECORD = "\x1e"
FIELD = "\x1f"

#: git reports "dubious ownership" when the repository lives on the WSL
#: filesystem and git is invoked from Windows. Harmless to pass everywhere.
GIT = ["git", "-c", "safe.directory=*", "-C", str(REPO_ROOT)]

REPRODUCE_COMMAND = (
    "git -c safe.directory='*' log --all --date=short --shortstat \\\n"
    "  --pretty=format:'%h %ad %an %d %s'"
)


def _run(*args: str) -> str:
    result = subprocess.run([*GIT, *args], capture_output=True, text=True, check=True)
    return result.stdout


def collect_commits() -> list[dict]:
    """Every commit reachable from any ref, newest first, with its shortstat."""
    raw = _run(
        "log", "--all", "--date=short", "--shortstat",
        f"--pretty=format:{RECORD}%h{FIELD}%ad{FIELD}%an{FIELD}%d{FIELD}%s",
    )

    commits: list[dict] = []
    for block in raw.split(RECORD)[1:]:
        # hash US date US author US decoration US subject, then the shortstat on
        # the following line when git emits one.
        parts = block.split(FIELD)
        if len(parts) < 5:
            continue
        short_hash, when, author, decoration = parts[0], parts[1], parts[2], parts[3]
        subject, _, stat_line = parts[4].partition("\n")

        commits.append(
            {
                "hash": short_hash.strip(),
                "date": when.strip(),
                "author": author.strip(),
                "decoration": decoration.strip(),
                "subject": subject.strip(),
                **parse_shortstat(stat_line),
            }
        )
    return commits


def parse_shortstat(text: str) -> dict:
    """Pull files/insertions/deletions out of git's --shortstat line.

    A merge commit produces no line at all: git's default diff for a merge is
    empty. Those keep None and render as an em dash, which is what the document
    has always shown rather than a misleading zero.
    """
    files = insertions = deletions = None
    match = re.search(r"(\d+) files? changed", text)
    if match:
        files = int(match.group(1))
        insertions = 0
        deletions = 0
        inserted = re.search(r"(\d+) insertions?\(\+\)", text)
        deleted = re.search(r"(\d+) deletions?\(-\)", text)
        if inserted:
            insertions = int(inserted.group(1))
        if deleted:
            deletions = int(deleted.group(1))
    return {"files": files, "insertions": insertions, "deletions": deletions}


def normalise_decoration(decoration: str) -> list[str]:
    """Branch and tag names, in a form a local run and a CI run both produce.

    Left raw, this column is unstable: a clone has ``HEAD -> main, origin/main,
    origin/HEAD`` where a CI checkout has something else, so a locally generated
    document and a CI generated one would rewrite each other on every run. The
    remote prefix, the ``HEAD ->`` marker and the symbolic ``origin/HEAD`` all
    describe the checkout rather than the history, so they are dropped and what
    remains is deduplicated and sorted.
    """
    inner = decoration.strip()
    if not inner:
        return []
    inner = inner.removeprefix("(").removesuffix(")")

    names: list[str] = []
    for ref in inner.split(","):
        ref = ref.strip()
        if not ref:
            continue
        ref = ref.removeprefix("HEAD -> ")
        if ref in ("HEAD", "origin/HEAD"):
            continue
        if ref.startswith("tag: "):
            names.append(ref)
            continue
        ref = ref.removeprefix("origin/")
        names.append(ref)

    return sorted(dict.fromkeys(names))


def format_row(commit: dict) -> str:
    if commit["files"] is None:
        files = EM_DASH
        churn = EM_DASH
    else:
        files = str(commit["files"])
        churn = f"+{commit['insertions']} / {MINUS}{commit['deletions']}"

    subject = commit["subject"]
    refs = normalise_decoration(commit["decoration"])
    if refs:
        subject = f"{subject} **[{', '.join(refs)}]**"

    return (
        f"| `{commit['hash']}` | {commit['date']} | {commit['author']} "
        f"| {files} | {churn} | {subject} |"
    )


def render(commits: list[dict], generated_on: str) -> str:
    by_month: "OrderedDict[str, list[dict]]" = OrderedDict()
    for commit in commits:
        by_month.setdefault(commit["date"][:7], []).append(commit)

    dates = [c["date"] for c in commits]
    total_files = sum(c["files"] or 0 for c in commits)
    total_insertions = sum(c["insertions"] or 0 for c in commits)
    total_deletions = sum(c["deletions"] or 0 for c in commits)

    main_branch = _run("rev-parse", "--abbrev-ref", "HEAD").strip() or "main"

    lines = [
        "# CrawlerNest — 完整 Commit 紀錄",
        "",
        f"產生於 {generated_on}，涵蓋所有分支（`git log --all`）。每筆附上該 commit 的檔案變更統計。",
        "",
        f"- **Commit 總數**：{len(commits)}",
        f"- **期間**：{min(dates)} ~ {max(dates)}",
        f"- **主分支**：`{main_branch}`",
        "",
        "## 欄位說明",
        "",
        "| 欄位 | 意義 |",
        "|---|---|",
        "| Commit | 短 hash；分支／tag 標記以粗體附在說明後 |",
        "| 檔案 | 該 commit 變更的檔案數 |",
        "| +/− | 新增／刪除行數 |",
        "| 說明 | commit subject（第一行） |",
        "",
        f"Merge commit 的統計為 `{EM_DASH}`：預設 diff 對 merge 不輸出 stat。",
        "",
        "## 重現指令",
        "",
        "```bash",
        REPRODUCE_COMMAND,
        "```",
        "",
        "repo 位於 WSL 檔案系統、git 由 Windows 端執行時，未加 `-c safe.directory='*'` 會出現 "
        "`dubious ownership` 錯誤。",
        "",
        "本檔由 `scripts/generate_commit_log.py` 產生；請勿手動編輯。",
        "",
        "---",
        "",
    ]

    for month, month_commits in by_month.items():
        lines += [
            f"## {month}",
            "",
            "| Commit | 日期 | 作者 | 檔案 | +/− | 說明 |",
            "|---|---|---|---|---|---|",
        ]
        lines += [format_row(c) for c in month_commits]
        lines.append("")

    lines += [
        "---",
        "",
        "## 總計",
        "",
        "| 項目 | 數值 |",
        "|---|---|",
        f"| Commit 數 | {len(commits)} |",
        f"| 檔案變更累計 | {total_files} |",
        f"| 新增行數累計 | +{total_insertions} |",
        f"| 刪除行數累計 | {MINUS}{total_deletions} |",
        f"| 淨增行數 | +{total_insertions - total_deletions} |",
        "",
    ]

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate docs/COMMIT_LOG.md.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit 1 if the committed document is out of date.",
    )
    parser.add_argument(
        "--generated-on",
        default=None,
        help="Override the generation date, so --check does not fail on the date alone.",
    )
    args = parser.parse_args()

    commits = collect_commits()
    if not commits:
        print("no commits found", file=sys.stderr)
        return 1

    existing = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.is_file() else ""

    generated_on = args.generated_on
    if generated_on is None:
        if args.check:
            # Compare content, not the day it was rendered.
            match = re.search(r"產生於 (\d{4}-\d{2}-\d{2})", existing)
            generated_on = match.group(1) if match else date.today().isoformat()
        else:
            generated_on = date.today().isoformat()

    rendered = render(commits, generated_on)

    if args.check:
        if existing == rendered:
            print(f"docs/COMMIT_LOG.md is current: {len(commits)} commits.")
            return 0
        recorded = re.search(r"\*\*Commit 總數\*\*：(\d+)", existing)
        recorded_count = int(recorded.group(1)) if recorded else 0
        print(
            f"docs/COMMIT_LOG.md is out of date: it records {recorded_count} commits, "
            f"the repository has {len(commits)}.\n"
            "Run: python3 scripts/generate_commit_log.py",
            file=sys.stderr,
        )
        return 1

    DOC_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"wrote {DOC_PATH.relative_to(REPO_ROOT)}: {len(commits)} commits, "
          f"{min(c['date'] for c in commits)} ~ {max(c['date'] for c in commits)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
