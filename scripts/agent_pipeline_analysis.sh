#!/usr/bin/env bash
# Optional wrapper for the sibling crawlernest-agents pipeline analysis workflow.
# Keeps crawlernest loosely coupled: no dependency, symlink, or submodule.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRAWLERNEST_REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PARENT_DIR="$(cd "${CRAWLERNEST_REPO_ROOT}/.." && pwd)"
AGENTS_REPO_ROOT="${CRAWLERNEST_AGENTS_REPO_ROOT:-${PARENT_DIR}/crawlernest-agents}"
AGENTS_PIPELINE_ANALYSIS="${AGENTS_REPO_ROOT}/scripts/generate-pipeline-analysis.py"
CRAWLERNEST_AGENT_OUTPUT_DIR="${CRAWLERNEST_REPO_ROOT}/tmp/agent-analysis"
DEFAULT_OUTPUT_FILE="${CRAWLERNEST_AGENT_OUTPUT_DIR}/pipeline-analysis-prompt.md"

log() {
  printf '[agent-pipeline-analysis] %s\n' "$*"
}

usage() {
  cat <<USAGE
Usage: ./scripts/agent_pipeline_analysis.sh <log_file> [output_file]

Creates a readonly pipeline analysis prompt using the sibling crawlernest-agents
tooling. The default output file is:
  ${DEFAULT_OUTPUT_FILE}

Allowed outputs:
  ${CRAWLERNEST_AGENT_OUTPUT_DIR}/
  ${AGENTS_REPO_ROOT}/tmp/
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -d "${AGENTS_REPO_ROOT}" ]]; then
  log "Optional crawlernest-agents repo was not found."
  log "Expected path: ${AGENTS_REPO_ROOT}"
  log "Place crawlernest-agents next to this repo to enable pipeline analysis."
  log "No changes were made."
  exit 0
fi

if [[ ! -f "${AGENTS_PIPELINE_ANALYSIS}" ]]; then
  log "crawlernest-agents exists, but the pipeline analysis tool was not found."
  log "Expected file: ${AGENTS_PIPELINE_ANALYSIS}"
  log "No changes were made."
  exit 1
fi

if [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
  usage
  exit 1
fi

LOG_FILE="$1"
OUTPUT_FILE="${2:-${DEFAULT_OUTPUT_FILE}}"

if [[ "${OUTPUT_FILE}" != /* ]]; then
  OUTPUT_FILE="${CRAWLERNEST_REPO_ROOT}/${OUTPUT_FILE}"
fi

OUTPUT_FILE="$(realpath -m "${OUTPUT_FILE}")"
AGENTS_TMP_DIR="$(realpath -m "${AGENTS_REPO_ROOT}/tmp")"
CRAWLERNEST_AGENT_OUTPUT_DIR="$(realpath -m "${CRAWLERNEST_AGENT_OUTPUT_DIR}")"

if [[ "${OUTPUT_FILE}" != "${CRAWLERNEST_AGENT_OUTPUT_DIR}/"* && "${OUTPUT_FILE}" != "${AGENTS_TMP_DIR}/"* ]]; then
  log "Output file must stay inside an allowed temporary directory."
  log "Allowed CrawlerNest output dir: ${CRAWLERNEST_AGENT_OUTPUT_DIR}"
  log "Allowed agents output dir: ${AGENTS_TMP_DIR}"
  log "Requested output file: ${OUTPUT_FILE}"
  log "No changes were made."
  exit 1
fi

mkdir -p "$(dirname "${OUTPUT_FILE}")" "${AGENTS_TMP_DIR}"

log "CrawlerNest repo: ${CRAWLERNEST_REPO_ROOT}"
log "Agents repo: ${AGENTS_REPO_ROOT}"
log "Mode: readonly analysis"
log "Input log: ${LOG_FILE}"
log "Output file: ${OUTPUT_FILE}"
log "Allowed CrawlerNest output dir: ${CRAWLERNEST_AGENT_OUTPUT_DIR}"
log "Agents may also write to their own tmp directory."

export CRAWLERNEST_REPO_ROOT
export CRAWLERNEST_AGENT_MODE="readonly"
export CRAWLERNEST_AGENT_OUTPUT_DIR

cd "${AGENTS_REPO_ROOT}"
python3 "${AGENTS_PIPELINE_ANALYSIS}" "${LOG_FILE}" "${OUTPUT_FILE}"
