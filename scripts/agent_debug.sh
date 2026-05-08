#!/usr/bin/env bash
# Optional wrapper for the sibling crawlernest-agents debug workflow.
# Keeps crawlernest loosely coupled: no dependency, symlink, or submodule.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRAWLERNEST_REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PARENT_DIR="$(cd "${CRAWLERNEST_REPO_ROOT}/.." && pwd)"
AGENTS_REPO_ROOT="${PARENT_DIR}/crawlernest-agents"
AGENTS_RUN_DEBUG="${AGENTS_REPO_ROOT}/scripts/run-debug.sh"
CRAWLERNEST_AGENT_OUTPUT_DIR="${CRAWLERNEST_REPO_ROOT}/tmp/agent-debug"

log() {
  printf '[agent-debug] %s\n' "$*"
}

if [[ ! -d "${AGENTS_REPO_ROOT}" ]]; then
  log "Optional crawlernest-agents repo was not found."
  log "Expected path: ${AGENTS_REPO_ROOT}"
  log "Place crawlernest-agents next to this repo to enable the debug workflow."
  log "No changes were made."
  exit 0
fi

if [[ ! -f "${AGENTS_RUN_DEBUG}" ]]; then
  log "crawlernest-agents exists, but the debug runner was not found."
  log "Expected file: ${AGENTS_RUN_DEBUG}"
  log "No changes were made."
  exit 1
fi

if [[ ! -x "${AGENTS_RUN_DEBUG}" ]]; then
  log "crawlernest-agents debug runner is not executable."
  log "Expected executable file: ${AGENTS_RUN_DEBUG}"
  log "Try: chmod +x ${AGENTS_RUN_DEBUG}"
  log "No changes were made."
  exit 1
fi

mkdir -p "${CRAWLERNEST_AGENT_OUTPUT_DIR}"

log "CrawlerNest repo: ${CRAWLERNEST_REPO_ROOT}"
log "Agents repo: ${AGENTS_REPO_ROOT}"
log "Mode: readonly analysis"
log "Allowed CrawlerNest output dir: ${CRAWLERNEST_AGENT_OUTPUT_DIR}"
log "Agents may also write to their own tmp directory."

export CRAWLERNEST_REPO_ROOT
export CRAWLERNEST_AGENT_MODE="readonly"
export CRAWLERNEST_AGENT_OUTPUT_DIR

cd "${AGENTS_REPO_ROOT}"
exec "${AGENTS_RUN_DEBUG}"
