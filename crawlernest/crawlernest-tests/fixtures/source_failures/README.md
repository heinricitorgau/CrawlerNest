# Source failure fixtures

One response per known way a ranking source fails, for `test_source_failure_fixtures.py`. Each is the smallest page
with the structure the crawler reads (THE: the `__NEXT_DATA__` table config; ARWU: the rendered page), modelled on
real responses rather than copied from them, so they carry no third-party content.

| File | Failure | Classification in run_status.json |
|---|---|---|
| `the_2026_ok.html` | none: the control | `ok` |
| `the_2026_serves_2025_table.html` | the 2026 address serves the 2025 table | `edition_mismatch` |
| `the_2026_layout_changed.html` | the page has no rankings table config | `layout_changed` |
| `the_2026_empty_table.html` | the verified table holds no rows | `empty_table` |
| `arwu_2026_no_table.html` | the ARWU page has no table | `layout_changed` |

Failures that are not a page (a 403 or 429, a 500, a lost connection, a truncated payload, a shrinking snapshot) are
built in the test itself. Add a fixture here when a source fails in a new way, with the classification it must get.
