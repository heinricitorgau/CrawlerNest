#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_ROOT="$(cd "${SCRIPT_DIR}" && pwd)"
PIPELINE="${RUNTIME_ROOT}/crawlernest/run_pipeline.py"
NODE_CONFIG="${RUNTIME_ROOT}/node_config.json"
LOG_DIR="${RUNTIME_ROOT}/logs"
DEFAULT_LOG_FILE=""
RESUME_MODE=false

usage() {
  cat <<'EOF'
Usage:
  ./run_lobster.sh [--resume] [--config path/to/node_config.json] [--log-file path]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume)
      RESUME_MODE=true
      shift
      ;;
    --config)
      NODE_CONFIG="$2"
      shift 2
      ;;
    --log-file)
      DEFAULT_LOG_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[lobster] Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "${NODE_CONFIG}" ]]; then
  echo "[lobster] Missing node config: ${NODE_CONFIG}" >&2
  exit 1
fi

if [[ ! -f "${PIPELINE}" ]]; then
  echo "[lobster] Missing pipeline entrypoint: ${PIPELINE}" >&2
  exit 1
fi

if [[ -d "${RUNTIME_ROOT}/.venv" ]]; then
  # shellcheck disable=SC1091
  source "${RUNTIME_ROOT}/.venv/bin/activate"
fi

if [[ -n "${DEFAULT_LOG_FILE}" ]]; then
  LOG_FILE="${DEFAULT_LOG_FILE}"
else
  mkdir -p "${LOG_DIR}"
  TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
  LOG_FILE="${LOG_DIR}/lobster_${TIMESTAMP}.log"
fi

exec > >(tee -a "${LOG_FILE}") 2>&1

json_get() {
  python3 - "$NODE_CONFIG" "$1" <<'PY'
import json
import sys

config_path, query = sys.argv[1], sys.argv[2]
with open(config_path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

value = payload
for part in query.split("."):
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break

if value is None:
    print("")
elif isinstance(value, bool):
    print("true" if value else "false")
else:
    print(value)
PY
}

append_flag_if_true() {
  local key="$1"
  local flag="$2"
  local value
  value="$(json_get "${key}")"
  if [[ "${value}" == "true" ]]; then
    PIPELINE_ARGS+=("${flag}")
  fi
}

echo "============================================================"
echo "[LOBSTER] Starting node pipeline at $(date '+%Y-%m-%d %H:%M:%S')"
echo "[LOBSTER] Runtime root : ${RUNTIME_ROOT}"
echo "[LOBSTER] Config       : ${NODE_CONFIG}"
echo "[LOBSTER] Log          : ${LOG_FILE}"
echo "============================================================"

NODE_ID="$(json_get "node_id")"
COMMAND_NAME="$(json_get "pipeline.command")"
RANKING_YEAR="$(json_get "pipeline.ranking_year")"
RANKING_LIMIT="$(json_get "pipeline.limit")"
RANKING_ID="$(json_get "pipeline.ranking_id")"
WORKERS="$(json_get "pipeline.workers")"
REQUEST_DELAY="$(json_get "pipeline.request_delay")"
LOCAL_PARSE_WORKERS="$(json_get "pipeline.local_parse_workers")"
WRITE_BATCH_SIZE="$(json_get "pipeline.write_batch_size")"
DETAIL_STREAK="$(json_get "pipeline.detail_403_streak_threshold")"
DETAIL_CHUNK_SIZE="$(json_get "pipeline.detail_chunk_size")"

PG_HOST="$(json_get "database.host")"
PG_PORT="$(json_get "database.port")"
PG_DATABASE="$(json_get "database.database")"
PG_USER="$(json_get "database.user")"
PG_PASSWORD="$(json_get "database.password")"

DEFERRED_ENABLED="$(json_get "deferred_enrichment.enabled")"
DEFERRED_LIMIT="$(json_get "deferred_enrichment.limit")"
DEFERRED_DELAY="$(json_get "deferred_enrichment.request_delay")"
DEFERRED_TIMEOUT="$(json_get "deferred_enrichment.timeout")"

RESUME_BY_DEFAULT="$(json_get "runtime_flags.resume_by_default")"
DEFERRED_FILE="${RUNTIME_ROOT}/crawlernest/crawlernest-kb/databases/pending_detail_enrichment.json"

if [[ -z "${COMMAND_NAME}" ]]; then
  COMMAND_NAME="run"
fi

PIPELINE_ARGS=(
  "${PIPELINE}"
  "${COMMAND_NAME}"
  "--ranking-year" "${RANKING_YEAR}"
  "--limit" "${RANKING_LIMIT}"
  "--ranking-id" "${RANKING_ID}"
  "--workers" "${WORKERS}"
  "--request-delay" "${REQUEST_DELAY}"
  "--local-parse-workers" "${LOCAL_PARSE_WORKERS}"
  "--write-batch-size" "${WRITE_BATCH_SIZE}"
  "--detail-403-streak-threshold" "${DETAIL_STREAK}"
  "--detail-chunk-size" "${DETAIL_CHUNK_SIZE}"
  "--pg-host" "${PG_HOST}"
  "--pg-port" "${PG_PORT}"
  "--pg-database" "${PG_DATABASE}"
  "--pg-user" "${PG_USER}"
  "--pg-password" "${PG_PASSWORD}"
)

append_flag_if_true "runtime_flags.use_async" "--use-async"
append_flag_if_true "runtime_flags.resource_guard" "--resource-guard"
append_flag_if_true "pipeline.rankings_only" "--rankings-only"

if [[ "${RESUME_MODE}" == true || "${RESUME_BY_DEFAULT}" == "true" ]]; then
  PIPELINE_ARGS+=("--resume")
fi

echo "[LOBSTER] Node ID      : ${NODE_ID}"
echo "[LOBSTER] Python       : $(command -v python3)"
echo "[LOBSTER] Command      : python3 ${PIPELINE_ARGS[*]}"

if ! python3 "${PIPELINE_ARGS[@]}"; then
  EXIT_CODE=$?
  echo "[lobster] Pipeline failed with exit code ${EXIT_CODE}" >&2
  exit "${EXIT_CODE}"
fi

if [[ "${DEFERRED_ENABLED}" == "true" && -f "${DEFERRED_FILE}" ]]; then
  if python3 - "${DEFERRED_FILE}" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
except Exception:
    raise SystemExit(1)

raise SystemExit(0 if isinstance(payload, list) and len(payload) > 0 else 1)
PY
  then
    echo "[LOBSTER] Deferred detail items found. Starting enrichment..."
    if ! python3 "${PIPELINE}" enrich-details \
      --limit "${DEFERRED_LIMIT}" \
      --request-delay "${DEFERRED_DELAY}" \
      --timeout "${DEFERRED_TIMEOUT}" \
      --deferred-details-file "${DEFERRED_FILE}" \
      --db-type postgres \
      --pg-host "${PG_HOST}" \
      --pg-port "${PG_PORT}" \
      --pg-database "${PG_DATABASE}" \
      --pg-user "${PG_USER}" \
      --pg-password "${PG_PASSWORD}"; then
      EXIT_CODE=$?
      echo "[lobster] Deferred enrichment failed with exit code ${EXIT_CODE}" >&2
      exit "${EXIT_CODE}"
    fi
  fi
fi

echo "============================================================"
echo "[LOBSTER] Node task finished at $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
