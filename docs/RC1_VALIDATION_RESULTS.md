# RC-1 Validation Results

Records the RC-1 operational validation run performed on 2026-05-16.

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

---

## Pass / Fail Summary

| Validation | Result | Notes |
| --- | --- | --- |
| `./scripts/verify_local_environment.sh` | Pass with warnings | `.venv` is healthy; system `python3` does not import `psycopg2`; ports 8080 and 3000 already in use because the local stack was running. |
| `bash scripts/smoke_release.sh` | Pass | 15 passed, 0 failed. |
| `cd crawlernest/crawlernest-web && npm run build` | Pass | Production build completed on Node 20.20.2. |
| `cd crawlernest/servise_for_java && ./mvnw test` | Pass | 84 tests passed. |
| Python syntax checks | Pass | `run_pipeline.py`, pipeline CLI, health / compare / snapshot scripts compiled successfully. |
| Readonly agent wrappers | Pass | `agent_context_snapshot.sh` and `agent_repo_prompt.sh` completed; outputs stayed under `tmp/agent-context/`. |
| Snapshot export | Pass | Wrote `snapshots/system_snapshot_20260516_125805.json` and refreshed `snapshots/latest_status.json`. |
| Snapshot comparison | Pass | Fixture comparison completed successfully with `compare_snapshots.py --json`. |
| `git diff --check` | Pass | No whitespace errors found. |
| Local Markdown link validation | Pass | RC-1 docs and index references resolve after adding this file. |

---

## Known Warnings

### Environment Warnings

- System `python3` does not import `psycopg2`, while `.venv/bin/python` does.
  RC-1 treats `.venv` as the canonical Python runtime.
- `verify_local_environment.sh` warns when ports 8080 and 3000 are already in
  use; during this run they were occupied by the running local stack.

### Operational State Warnings

Readonly pipeline health completed with `status=stale`:

- latest aggregation age: about 206.6 hours
- expected-source gaps: `THE`, `ARWU`
- duplicate resolution saves observed: `3`
- latest subject year: missing

These are current data-state warnings, not validation-script failures. They are
acceptable for RC-1 only as explicitly known limitations; they should be called
out before a demo that claims data freshness or multi-source completeness.

---

## Validation Notes

- `smoke_release.sh` was hardened during RC-1 to prefer `.venv/bin/python`
  when available and to provide the local PostgreSQL password default used by
  the documented localhost setup. This is a readonly validation-helper change;
  it does not alter runtime application behavior.
- The first sandboxed frontend build attempt failed because Turbopack could not
  bind a local helper port inside the sandbox. The production build passed when
  rerun outside the sandbox.
- The first sandboxed Maven test attempt failed because Mockito / ByteBuddy test
  instrumentation could not initialize under sandbox limits. The full suite
  passed when rerun outside the sandbox.
- Snapshot export requires a live readonly PostgreSQL connection and therefore
  was run through `.venv/bin/python` with the documented localhost credentials.

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
