# CrawlerNest v0.3 — Multi-Year Release Snapshot

**Release label:** `v0.3-multi-year-snapshot`
**Freeze date:** 2026-11-11

The first reproducible baseline holding more than one edition: THE and ARWU 2015–2026, QS 2016, 2018–2020
and 2022–2026, 27,409 aggregated rows, the US federal institutional data, the Wikipedia introductions and the
entity-resolution repairs of October 2026. Counts and checksum are in [manifest.json](manifest.json); restore
with the command in [README.md](README.md).

Release verification is now a contract rather than a script per release: every release directory carries a
`manifest.json`, `scripts/restore_release_snapshot.sh` reads whichever one `RELEASE_DIR` names, and the
release-snapshot CI job restores each release. This dump carries no user data.

Partial coverage stays partial: a missing source rank is a gap in this warehouse, never a source declining to
rank, and every analytics response still carries its `caveats`.
