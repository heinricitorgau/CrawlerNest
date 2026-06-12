# RC-1 Validation Results

Records the RC-1 operational validation run performed on 2026-05-22.

---

## Environment Used

| Component | Observed |
| --- | --- |
| OS | Ubuntu 24.04 on WSL2 (`amd64`) |
| Java | OpenJDK 17.0.18 |
| Maven | 3.9.6 via `./mvnw` |
| Node.js | 20.20.2 |
| npm | 10.8.2 |
| Python | 3.12.3 |
| PostgreSQL | 16.13 |
| Python runtime used for DB scripts | repo-root `.venv/bin/python` |
| Validation timestamp | 2026-05-22 23:28-23:32 Asia/Taipei |

---

## Pass / Fail Summary

| Validation | Result | Notes |
| --- | --- | --- |
| `./scripts/verify_local_environment.sh` | Pass with warnings | `.venv` is healthy; system `python3` does not import `psycopg2`; ports 8080 and 3000 were available. |
| `./scripts/smoke_release.sh` | Pass | 10 passed, 0 failed; API endpoint checks were skipped because Spring Boot was not running. |
| `cd crawlernest/crawlernest-web && npm run build` | Pass | Production build completed on Node 20.20.2 with Next.js 16.2.6. |
| `cd crawlernest/servise_for_java && ./mvnw test` | Pass | 84 tests passed, 0 failures, 0 errors, 0 skipped. |
| Python syntax checks | Pass | `run_pipeline.py`, pipeline CLI, health / compare / snapshot scripts compiled successfully. |
| Readonly agent wrappers | Pass | `agent_context_snapshot.sh` and `agent_repo_prompt.sh` completed; outputs stayed under `tmp/agent-context/`. |
| Snapshot export | Pass | Wrote `snapshots/system_snapshot_20260522_152944.json` and refreshed `snapshots/latest_status.json`. Required elevated local execution because sandboxed commands could not connect to localhost PostgreSQL. |
| Snapshot comparison | Pass | Fixture comparison completed successfully with `compare_snapshots.py --json`. |
| `git diff --check` | Pass | No whitespace errors found after RC-1 doc updates. |
| Local Markdown link validation | Pass | Local relative Markdown links resolve across tracked project docs. |

---

## Known Warnings

### Environment Warnings

- System `python3` does not import `psycopg2`, while `.venv/bin/python` does.
  RC-1 treats `.venv` as the canonical Python runtime.
- Sandboxed commands could not open a local PostgreSQL connection for snapshot
  export. The same readonly snapshot command passed when allowed to connect to
  local PostgreSQL directly.

### Operational State Warnings

Readonly pipeline health completed with `status=stale`:

- latest aggregation age: about 353.1-353.2 hours
- expected-source gaps: `THE`, `ARWU`
- duplicate resolution saves observed: `3`
- latest subject year: missing

These are current data-state warnings, not validation-script failures. They are
acceptable for RC-1 only as explicitly known limitations; they should be called
out before a demo that claims data freshness or multi-source completeness.

---

## Validation Notes

- `smoke_release.sh` used `.venv/bin/python` automatically, which kept DB-aware
  diagnostics on the canonical Python runtime.
- Maven test output includes verbose Spring Boot debug and condition-report
  logging plus Hibernate warnings. These are noisy but not failures.
- `check_pipeline_health.py` reported `status=stale`, while the compact
  snapshot export status reported `overall_stale=false`. This is a known
  validation-surface inconsistency to review after RC-1; no diagnostics
  semantics were changed during this pass.
- Snapshot export requires a live readonly PostgreSQL connection and was run
  through `.venv/bin/python` with the documented localhost credentials.

---

## Acceptable Limitations For RC-1

- Local demo topology only: localhost PostgreSQL, Spring Boot, and Next.js.
- Session persistence remains in-memory and is lost on API restart.
- Current live data is not fresh and does not yet show all expected sources.
- No native Windows validation, no Docker Compose path, and no multi-node
  deployment validation are included in this RC-1 pass.

---

## RC-1 Validation Conclusion

The codebase is operationally buildable, testable, and repeatably verifiable
under the frozen local environment. RC-1 is suitable for a controlled early
release candidate and stable demo baseline, provided the stale / incomplete
live data state is presented honestly and not mistaken for a code-health issue.
