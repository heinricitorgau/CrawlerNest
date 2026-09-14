# Scheduled refresh

The pipeline runs from a host scheduler, never from the serving stack. The
Spring Boot API and the Next.js app are read-only and cannot start it;
`crawlernest-tests/test_no_pipeline_triggers_from_api.py` fails if either gains
a way to.

| File | Purpose |
|---|---|
| `crawlernest-scheduled-refresh.service` | oneshot: `python -m crawlernest.run_pipeline scheduled-refresh` |
| `crawlernest-scheduled-refresh.timer` | weekly, Monday 03:30 ± 45 min, catches up after downtime |
| `install_scheduler.sh` | installs both as systemd user units and enables the timer |

```bash
deploy/scheduler/install_scheduler.sh --repo ~/dev/University-Data-Infrastructure-Web-Platform
```

## What a run does

`scheduled-refresh` refreshes the newest edition `crawlernest/core/dataset.py`
holds, once, for QS (global), THE and ARWU:

- each source proves the edition from its own page before a row is labelled
  (`crawlernest-jobs/ranking_edition.py`);
- a batch that would prune most of an edition is refused
  (`MultiSourceRankingPipeline.ingest_records`, `MIN_RETAINED_RATIO`);
- the legacy seed/backfill is skipped;
- sources are isolated, a lock prevents overlap, and the exit code is non-zero
  if any source failed.

Status: `~/.crawlernest/scheduled_refresh/scheduled_refresh_latest.json`, log
beside it, and `systemctl --user status crawlernest-scheduled-refresh`.

## Why not `run_pipeline run`

`run` defaults to `--limit 30` and rewrites QS world ranks from the legacy table,
so on a held edition it pruned everything the 30-row crawl did not carry. It
also discards the printed rank that per-source rank movement needs, and
`run-qs-universes` loops forever. See
`crawlernest/pipeline/commands/scheduled_refresh.py`.

## WSL

systemd user units run only while the WSL VM is up. `Persistent=true` runs a
missed pass at the next start. For unattended runs with no open session, enable
lingering (`loginctl enable-linger $USER`) and keep the VM running.
