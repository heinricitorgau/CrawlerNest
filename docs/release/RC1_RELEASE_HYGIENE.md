# RC-1 Release Hygiene

Documents the repository hygiene boundary for the RC-1 freeze. This review does
not restructure the repository or change runtime behavior.

---

## Git-Excluded Runtime And Build Outputs

| Path / Pattern | Policy | Status |
| --- | --- | --- |
| `node_modules/` | Local install output only | Ignored |
| `.next/` | Next.js build output only | Ignored |
| `target/`, `*.class` | Maven / Java build output only | Ignored |
| `.venv/`, `.venv-1/` | Local Python environments only | Ignored |
| `snapshots/` | Runtime operational evidence | Ignored |
| `reports/` | Runtime generated reports | Ignored |
| `backups/` | Runtime backup bundles / dumps | Ignored |
| `tmp/` | Temporary prompts, agent wrapper outputs, local scratch files | Ignored in RC-1 |

`git ls-files` currently returns no tracked files under `tmp/`, `snapshots/`,
`reports/`, `backups/`, or `crawlernest/servise_for_java/target/`.

---

## Snapshots, Reports, And Backups Policy

- `snapshots/` contains generated point-in-time system JSON such as
  `system_snapshot_*.json` and `latest_status.json`.
- `reports/` contains generated human-readable operational summaries.
- `backups/` contains generated metadata bundles and database backup artifacts.
- These directories are runtime evidence, not source-controlled release inputs.
- Retention guidance remains in `SCHEDULED_OPERATIONS.md` and
  `OPERATIONAL_RECOVERY.md`; RC-1 keeps that policy intact rather than moving
  generated evidence into Git.

---

## Temporary Artifacts Policy

- `tmp/agent-context/`, `tmp/agent-debug/`, and `tmp/agent-analysis/` are
  deliberate readonly-wrapper output locations.
- Root-level `tmp/` is ignored as a whole so local agent prompts, smoke helper
  scratch files, and one-off inspection outputs do not drift into commits.
- The sibling `crawlernest-agents` repository may keep its own temporary files
  under its own `tmp/`; those are outside this repository boundary.

---

## RC-1 Conclusion

The current repository hygiene is suitable for RC-1 after the minimal ignore
hardening above. Build outputs, local environments, runtime evidence, and
temporary helper artifacts are excluded from source control without changing
the repository layout.
