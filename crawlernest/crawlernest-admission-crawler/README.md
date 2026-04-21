# crawlernest-admission-crawler

Admission-specific crawler engine for CrawlerNest.

This module is responsible for:

- crawling university websites
- discovering admission-related pages
- extracting admission requirements such as IELTS and TOEFL
- handling unstructured and semi-structured admissions content

It should depend on `crawlernest-crawler-core/`, but it must not depend on the ranking crawler engine.

`crawlernest-crawler-core/` should be treated here as a shared runtime dependency that may evolve on a different cadence, but only for reusable crawler primitives rather than admission-specific extraction policy.

## Files

- `engine.py`: admission engine entrypoint
- `models.py`: `AdmissionRecord`
- `crawlers/university_site.py`: example university-site crawler stub
- `extractors/admission_requirements.py`: lightweight admission record helper
- `site_profiles/default.py`: starter admission keyword profile
