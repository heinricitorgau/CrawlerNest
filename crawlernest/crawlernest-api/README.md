# crawlernest-api (legacy)

Leftovers of an early prototype; nothing imports, builds or deploys this folder. The serving API is
`crawlernest/servise_for_java/` (Spring Boot, port 8080) and the agent API is
`crawlernest/interfaces/api/agent_api/` (port 8090).

`src/app.py` was removed on 2026-11-12. It was a FastAPI app whose `POST /run-crawler` ran
`run_pipeline.py run` with no authentication: a pipeline trigger over HTTP, which this project forbids
(`.claude/CLAUDE.md`, "no pipeline triggers from the API layer"). It was never deployed, but it could be
started by hand, and the guard test did not look at Python.
`crawlernest-tests/test_no_pipeline_triggers_from_api.py` now scans every Python HTTP server as well.

What remains (`src/app/page.tsx`, `src/lib/api.ts`, `src/types/rankings.ts`) is an old copy of a rankings page.
