## Summary

<!-- What does this PR change and why? -->

## Checklist

### CI / Build
- [ ] `release-smoke` workflow passes (Spring Boot compile + Next.js build + Python syntax)
- [ ] `data-quality` workflow passes (regression fixture mode + failure summary)
- [ ] `npm run build` completes without errors

### Data Integrity
- [ ] No schema changes — or schema migration is included and backward-compatible
- [ ] No changes to aggregation formula — or the change is intentional and documented in this PR
- [ ] `golden.json` updated if expected ranks/countries changed

### Regression
- [ ] `run_ranking_regression.py --fixture-file datasets/ci_fixtures/db_state.json` passes locally
- [ ] No new source drift warnings introduced (or existing ones are explained)

### Operational
- [ ] `smoke_release.sh` passes locally
- [ ] `docs/` updated if new scripts, pipelines, or scheduled operations were added
- [ ] `.gitignore` covers any new runtime artifacts (logs, snapshots, build outputs)
