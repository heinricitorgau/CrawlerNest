# Demo Honesty Guidelines

Use these guidelines when presenting CrawlerNest while maintenance reports show
freshness or source limitations.

---

## Caveats That Must Be Stated

- Ranking data freshness is currently critical/stale.
- QS is present but stale.
- THE and ARWU are currently unavailable in the latest source coverage.
- Subject ranking completeness is limited in the latest snapshot.
- This is a localhost/single-node demo posture, not production deployment.
- Sessions are in-memory; API restart signs users out.

---

## Warnings Not To Soften

- Do not soften `critical` freshness into "mostly healthy."
- Do not present missing sources as "temporarily hidden."
- Do not imply fallback data stands in for unavailable sources.
- Do not claim production readiness from local smoke success.

---

## Acceptable Phrasing

- "THE/ARWU are currently unavailable in the latest source coverage."
- "Ranking freshness is currently degraded/critical, so this is a scoped demo."
- "QS data is present but stale."
- "The release smoke passes, but freshness caveats remain."
- "This validates the app path, not production-grade data freshness."

---

## Unacceptable Phrasing

- "All ranking sources are healthy."
- "Production-ready global coverage."
- "Fresh multi-source ranking data is fully available."
- "The system repaired source gaps automatically."
- "Missing sources are safely substituted."

---

## Presenter Checklist

1. Read `reports/demo_caveats.md`.
2. Confirm smoke result from `reports/operational_trust_summary.md` or bundle output.
3. State data freshness and source caveats before showing rankings.
4. Avoid broad source completeness claims.
