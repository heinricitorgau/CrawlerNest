# Frontend API Mapping

This reference maps the current frontend surfaces to the backend API groups used
by CrawlerNest. It is intentionally compact; detailed endpoint summaries live in
[../API_SURFACE.md](../API_SURFACE.md).

## Main Surfaces

| Frontend area | Backend API group | Purpose |
| --- | --- | --- |
| `/rankings` | Rankings API | Lists aggregated university rankings and ranking detail views. |
| `/universities/[slug]` | Universities API | Shows canonical university detail and ranking context. |
| `/universities/[slug]/sources` | Explainability API | Shows source comparison, confidence, disagreement, and contribution data. |
| `/subjects` | Subject Rankings API | Lists subject-specific ranking slices and subject detail views. |
| `/recommendations` | Recommendation API | Surfaces recommendation results without changing ranking aggregation. |
| `/system-status` | Health, freshness, diagnostics APIs | Shows health, freshness, drift, ingestion, and source agreement status. |
| `/data-quality` | Diagnostics API | Shows quality checks, coverage, and disagreement outliers. |

## Notes

- Frontend pages should consume explainability endpoints as metadata only.
- Aggregation, recommendation scoring, and canonical matching rules remain backend-owned.
- Operational dashboards should prefer diagnostics endpoints over duplicating checks in the UI.
