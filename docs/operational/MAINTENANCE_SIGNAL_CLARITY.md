# Maintenance Signal Clarity

This document clarifies which operational signals are authoritative, derived,
demo-facing, maintenance-facing, or escalation-facing.

---

## Signal Classes

| Signal | Class | Notes |
| --- | --- | --- |
| PostgreSQL runtime state | Authoritative runtime state | Live application data source. |
| API diagnostics | Authoritative live diagnostics | GET-only runtime observation. |
| `.local/snapshots/*.json` | Historical evidence | Point-in-time, not live authority. |
| `.local/reports/freshness_escalation.md` | Escalation-facing derived report | Best freshness escalation read. |
| `.local/reports/drift_timeline.md` | Escalation-facing derived report | Best drift severity read. |
| `.local/reports/maintenance_readiness_summary.md` | Maintenance-facing derived report | Best maintenance caveat/confidence read. |
| `.local/reports/demo_caveats.md` | Demo-facing derived report | Best presenter caveat read. |
| `.local/reports/operational_trust_summary.md` | Trust-facing derived report | Best confidence rollup. |
| `smoke_release_output.txt` | Release validation evidence | Build/smoke status, not data freshness. |

---

## Maintainer Reading Order

1. `./scripts/maintenance_overview.sh`
2. `.local/reports/operational_trust_summary.md`
3. `.local/reports/maintenance_readiness_summary.md`
4. `.local/reports/freshness_escalation.md`
5. `.local/reports/drift_timeline.md`
6. `docs/SOURCE_FRESHNESS_RECOVERY.md`

---

## Release / Demo Reading Order

1. `.local/reports/demo_caveats.md`
2. `.local/reports/operational_trust_summary.md`
3. `.local/reports/operational_index_summary.md`
4. `docs/releases/v0.1-demo/smoke_release_output.txt`
5. `docs/DEMO_HONESTY_GUIDELINES.md`

---

## Boundary

Derived reports guide human decisions. They do not enforce runtime health,
automatically gate releases, repair source gaps, or mutate data.
