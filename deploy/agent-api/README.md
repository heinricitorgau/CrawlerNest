# Agent API

The Python agent API (`crawlernest/interfaces/api/agent_api/`) is a Starlette
ASGI app served by Uvicorn. It replaced a `ThreadingHTTPServer` that had one
unbounded thread per connection, no graceful shutdown, and a single process.

```bash
# local, one worker, JSON state under ~/.local/state/crawlernest/agent
PYTHONPATH=. ./.venv/bin/python -m crawlernest.interfaces.api.agent_api

# production shape: several workers, state in PostgreSQL
CRAWLERNEST_AGENT_STORE_BACKEND=postgres \
CRAWLERNEST_AGENT_DATABASE_URL=postgresql://crawlernest_agent@localhost:5432/clawer \
PYTHONPATH=. ./.venv/bin/python -m crawlernest.interfaces.api.agent_api --workers 2
```

| File | Purpose |
|---|---|
| `crawlernest-agent-api.service` | systemd user unit; restarts on failure, graceful stop |
| `agent-api.env.example` | every setting, no secrets; copy to `~/.config/crawlernest/agent-api.env` |

## State

| Backend | Where | Workers |
|---|---|---|
| `json` (default) | one file per store in `CRAWLERNEST_AGENT_STATE_DIR` (default `~/.local/state/crawlernest/agent`), written atomically | 1 only |
| `postgres` | schema `agent_state` (`crawlernest/crawlernest-schema/agent_state_postgresql.sql`) | any |

The server refuses `--workers` above 1 on the JSON backend. Each worker would
keep its own conversation history, so a follow-up could land on a worker that
never saw the question before it, and whole-file JSON rewrites from several
processes lose updates.

The postgres backend needs the schema first. `bootstrap-postgres` applies it,
and each worker checks for it at start-up and exits if it is missing:

```bash
python3 -m crawlernest.run_pipeline bootstrap-postgres --pg-user test --pg-database clawer
```

Give the agent its own role, limited to that schema:

```sql
CREATE ROLE crawlernest_agent LOGIN;  -- password via \password, stored in ~/.pgpass
GRANT USAGE ON SCHEMA agent_state TO crawlernest_agent;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA agent_state TO crawlernest_agent;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA agent_state TO crawlernest_agent;
```

The agent's tools also read the warehouse directly, through
`crawlernest/core/services` and `CRAWLERNEST_PG_*` (a separate connection that
opens per query). Point that at a read-only role (`SELECT` on `warehouse` and
`analytics`), not at `crawlernest_agent`. `DatabaseSettings` still falls back to
`test`/`test` when those variables are unset; removing that fallback belongs to
the secrets-management step, not this one.

## Endpoints

| Route | Meaning |
|---|---|
| `GET /health` | liveness; touches no dependency |
| `GET /health/ready` | readiness; 503 when the state database is unreachable |
| `GET /api/v1/agent/stats` | generation and verification counters for the worker that answered, with caveats saying so |
| `POST /api/v1/agent/tasks`, `POST /api/v1/agent/explain` | unchanged |

## Limits

- Request body: `CRAWLERNEST_AGENT_API_MAX_REQUEST_BYTES` (413), enforced on
  chunked bodies too.
- Concurrency: `--limit-concurrency` per worker; beyond it Uvicorn answers 503
  rather than queueing without bound.
- Handlers run on a thread pool, so a slow model call does not stall `/health`
  or other requests.
- Shutdown: SIGTERM stops accepting and gives in-flight requests
  `--graceful-timeout` seconds.
