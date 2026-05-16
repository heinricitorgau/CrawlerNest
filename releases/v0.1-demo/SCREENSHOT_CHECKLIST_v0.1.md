# CrawlerNest v0.1 — Screenshot Checklist

Use this checklist when capturing demo or milestone screenshots. Required screenshots should be taken before any public handover or demo. Optional screenshots add depth. Each entry includes route or command, recommended viewport, and recommended filename.

---

## Required Screenshots

These screenshots represent the minimum visual evidence for a v0.1 demo package.

### 1. Global Rankings Page

| Field | Value |
|-------|-------|
| Route | `http://localhost:3000/rankings` |
| Command | Open in browser after starting services |
| Viewport | 1440 × 900 |
| State | Table populated, top 10 rows visible, pagination controls showing |
| Filename | `rankings_global_top10.png` |

**What to show:** Rank column, university name, country, composite score, source count. Capture the top 10 rows.

---

### 2. Subject Rankings Page — Computer Science

| Field | Value |
|-------|-------|
| Route | `http://localhost:3000/subject-rankings` |
| Command | Select "Computer Science" from subject dropdown |
| Viewport | 1440 × 900 |
| State | Subject selector on "Computer Science", results table populated |
| Filename | `rankings_subject_cs.png` |

**What to show:** Subject selector, ranked list with university names, country, rank, subject label.

---

### 3. System Status Page — Full View

| Field | Value |
|-------|-------|
| Route | `http://localhost:3000/system-status` |
| Command | Open in browser |
| Viewport | 1440 × 900 |
| State | All sections loaded: Health, Freshness, Rankings Diagnostics, Subject Coverage |
| Filename | `system_status_full.png` |

**What to show:** postgres_connected badge, freshness FRESH badges, aggregated count, subject row counts.

---

### 4. Health API Response

| Field | Value |
|-------|-------|
| Route | `http://localhost:8080/api/v1/health` |
| Command | `curl -s http://localhost:8080/api/v1/health \| python3 -m json.tool` |
| Viewport | Terminal (80-column width recommended) |
| State | `postgres_connected: true`, counts visible |
| Filename | `api_health_terminal.png` |

**What to show:** `status: "ok"`, `postgres_connected: true`, `aggregated_ranking_count`.

---

### 5. Release Smoke Test Pass

| Field | Value |
|-------|-------|
| Route | N/A — terminal |
| Command | `./scripts/smoke_release.sh` |
| Viewport | Terminal (full output visible) |
| State | All 8 steps passed, final line "Release smoke passed." |
| Filename | `smoke_release_pass.png` |

**What to show:** Each `OK   ...` line for all 8 steps, final pass summary. `Results: N passed, 0 failed`.

---

## Optional Screenshots

These add completeness to a demo package but are not required for baseline evidence.

### 6. University Detail Page

| Field | Value |
|-------|-------|
| Route | `http://localhost:3000/universities/{slug}` |
| Command | Click any university in the rankings list |
| Viewport | 1440 × 900 |
| State | Detail page with composite score, source breakdown, admission signals |
| Filename | `university_detail.png` |

---

### 7. Recommendations Page

| Field | Value |
|-------|-------|
| Route | `http://localhost:3000/recommendations` |
| Command | Open with default filters |
| Viewport | 1440 × 900 |
| State | Reach / Target / Safety groups populated |
| Filename | `recommendations_groups.png` |

---

### 8. Subject Rankings — Electrical Engineering

| Field | Value |
|-------|-------|
| Route | `http://localhost:3000/subject-rankings` |
| Command | Select "Electrical Engineering" from dropdown |
| Viewport | 1440 × 900 |
| State | EE results loaded |
| Filename | `rankings_subject_ee.png` |

---

### 9. Rankings Page — Country Filter Applied

| Field | Value |
|-------|-------|
| Route | `http://localhost:3000/rankings` |
| Command | Apply country filter (e.g., United States) |
| Viewport | 1440 × 900 |
| State | Filtered results for selected country |
| Filename | `rankings_country_filter.png` |

---

## Operational Screenshots

Capture these to document system state at time of milestone.

### 10. Snapshot Status JSON

| Field | Value |
|-------|-------|
| Route | N/A — terminal |
| Command | `cat snapshots/latest_status.json \| python3 -m json.tool` |
| Viewport | Terminal |
| State | Shows aggregated_count, source_counts, unresolved_total, overall_stale |
| Filename | `snapshot_latest_status.png` |

---

### 11. Failure Summary Report

| Field | Value |
|-------|-------|
| Route | N/A — terminal |
| Command | `cat reports/latest_failure_summary.md` |
| Viewport | Terminal |
| State | Shows overall status table, unresolved count, staleness, regression coverage |
| Filename | `failure_summary_report.png` |

---

### 12. Pipeline Health Check

| Field | Value |
|-------|-------|
| Route | N/A — terminal |
| Command | `python3 scripts/check_pipeline_health.py` |
| Viewport | Terminal |
| State | Readonly diagnostic output |
| Filename | `pipeline_health_check.png` |

---

## Diagnostics Screenshots

### 13. Data Quality API Response

| Field | Value |
|-------|-------|
| Route | `http://localhost:8080/api/v1/diagnostics/data-quality` |
| Command | `curl -s http://localhost:8080/api/v1/diagnostics/data-quality \| python3 -m json.tool` |
| Viewport | Terminal |
| State | unresolved_count: 4, drift_warning_count: 0 |
| Filename | `api_diagnostics_data_quality.png` |

---

### 14. Source Agreement API Response

| Field | Value |
|-------|-------|
| Route | `http://localhost:8080/api/v1/diagnostics/source-agreement` |
| Command | `curl -s http://localhost:8080/api/v1/diagnostics/source-agreement \| python3 -m json.tool` |
| Viewport | Terminal |
| State | QS/THE rank difference metrics, outliers, source overlap |
| Filename | `api_diagnostics_source_agreement.png` |

---

### 15. Rankings Diagnostics API

| Field | Value |
|-------|-------|
| Route | `http://localhost:8080/api/v1/diagnostics/rankings` |
| Command | `curl -s http://localhost:8080/api/v1/diagnostics/rankings \| python3 -m json.tool` |
| Viewport | Terminal |
| State | aggregated_count, latest_run_id, api_ready: true |
| Filename | `api_diagnostics_rankings.png` |

---

## CI Screenshots

### 16. GitHub Actions — Release Smoke Green

| Field | Value |
|-------|-------|
| Route | GitHub Actions tab, `release-smoke` workflow |
| Command | Navigate to latest successful run |
| Viewport | 1440 × 900 browser |
| State | All steps green, no failures |
| Filename | `ci_release_smoke_green.png` |

---

### 17. GitHub Actions — Data Quality Green

| Field | Value |
|-------|-------|
| Route | GitHub Actions tab, `data-quality` workflow |
| Command | Navigate to latest successful run |
| Viewport | 1440 × 900 browser |
| State | All steps green including regression fixture |
| Filename | `ci_data_quality_green.png` |

---

### 18. Local CI Reproduction

| Field | Value |
|-------|-------|
| Route | N/A — terminal |
| Command | `bash scripts/run_ci_locally.sh` |
| Viewport | Terminal |
| State | Smoke + fixture regression + failure summary all pass |
| Filename | `ci_local_reproduction.png` |

---

## Explainability Screenshots

### 19. Rankings Explainability API Response

| Field | Value |
|-------|-------|
| Route | `http://localhost:8080/api/v1/rankings/{id}/explain` |
| Command | (see DEMO_SCRIPT_v0.1.md Section 5 for command) |
| Viewport | Terminal |
| State | source_contributions, weighted_inputs, formula_note visible |
| Filename | `api_explain_ranking.png` |

---

### 20. Source Comparison API Response

| Field | Value |
|-------|-------|
| Route | `http://localhost:8080/api/v1/universities/{id}/source-comparison` |
| Command | (see DEMO_SCRIPT_v0.1.md Section 5 for command) |
| Viewport | Terminal |
| State | QS and THE ranks, rank_spread, confidence visible |
| Filename | `api_source_comparison.png` |

---

## System Status Screenshots

### 21. Freshness API Response

| Field | Value |
|-------|-------|
| Route | `http://localhost:8080/api/v1/freshness` |
| Command | `curl -s http://localhost:8080/api/v1/freshness \| python3 -m json.tool` |
| Viewport | Terminal |
| State | overall_stale: false, per-source FRESH status |
| Filename | `api_freshness.png` |

---

### 22. System Status — Health Section Only

| Field | Value |
|-------|-------|
| Route | `http://localhost:3000/system-status` |
| Command | Scroll to Health Overview section |
| Viewport | 1440 × 900, crop to health section |
| State | postgres_connected: true badge visible |
| Filename | `system_status_health_section.png` |

---

## Screenshot Storage Convention

Store screenshots under:

```
releases/v0.1-demo/screenshots/
```

Use the filenames specified above. If a screenshot cannot be captured (service not running, endpoint not reachable), create a placeholder file:

```bash
echo "[missing — service not running at capture time]" > releases/v0.1-demo/screenshots/FILENAME.txt
```

---

## Priority Order

| Priority | Screenshots |
|----------|------------|
| Must-have | 1, 2, 3, 4, 5 |
| Operational evidence | 10, 11, 12 |
| Diagnostics | 13, 14, 15 |
| CI evidence | 16, 17 |
| Explainability | 19, 20 |
| Extended | 6, 7, 8, 9, 18, 21, 22 |
