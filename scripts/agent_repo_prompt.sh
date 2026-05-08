#!/usr/bin/env bash
# Generate a repo-aware readonly prompt through the sibling crawlernest-agents repo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PARENT_DIR="$(cd "${REPO_ROOT}/.." && pwd)"
AGENTS_REPO_ROOT="${CRAWLERNEST_AGENTS_REPO_ROOT:-${PARENT_DIR}/crawlernest-agents}"
PROMPT_GENERATOR="${CRAWLERNEST_AGENT_PROMPT_GENERATOR:-${AGENTS_REPO_ROOT}/scripts/generate-debug-prompt.py}"

CONTEXT_DIR="${REPO_ROOT}/tmp/agent-context"
DEBUG_DIR="${REPO_ROOT}/tmp/agent-debug"
ANALYSIS_DIR="${REPO_ROOT}/tmp/agent-analysis"
CONTEXT_SNAPSHOT="${CONTEXT_DIR}/context_snapshot.md"
PROMPT_INPUT="${CONTEXT_DIR}/repo_prompt_input.md"
DEFAULT_OUTPUT_FILE="${CONTEXT_DIR}/repo-aware-prompt.md"

log() {
  printf '[agent-repo-prompt] %s\n' "$*"
}

usage() {
  cat <<USAGE
Usage: ./scripts/agent_repo_prompt.sh [log_or_note_file] [output_file]

Builds tmp/agent-context/context_snapshot.md, injects that path into a readonly
prompt input, then calls the sibling crawlernest-agents prompt generator.

Allowed outputs:
  ${CONTEXT_DIR}/
  ${DEBUG_DIR}/
  ${ANALYSIS_DIR}/
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
  log "Place crawlernest-agents next to this repo to enable repo-aware prompts."
  log "No changes were made."
  exit 0
fi

if [[ ! -f "${PROMPT_GENERATOR}" ]]; then
  log "crawlernest-agents exists, but the prompt generator was not found."
  log "Expected file: ${PROMPT_GENERATOR}"
  log "No changes were made."
  exit 1
fi

if [[ "$#" -gt 2 ]]; then
  usage
  exit 1
fi

NOTE_FILE="${1:-}"
OUTPUT_FILE="${2:-${DEFAULT_OUTPUT_FILE}}"

if [[ -n "${NOTE_FILE}" && "${NOTE_FILE}" != /* ]]; then
  NOTE_FILE="${REPO_ROOT}/${NOTE_FILE}"
fi

if [[ "${OUTPUT_FILE}" != /* ]]; then
  OUTPUT_FILE="${REPO_ROOT}/${OUTPUT_FILE}"
fi

OUTPUT_FILE="$(realpath -m "${OUTPUT_FILE}")"
CONTEXT_DIR="$(realpath -m "${CONTEXT_DIR}")"
DEBUG_DIR="$(realpath -m "${DEBUG_DIR}")"
ANALYSIS_DIR="$(realpath -m "${ANALYSIS_DIR}")"
AGENTS_TMP_DIR="$(realpath -m "${AGENTS_REPO_ROOT}/tmp")"

if [[ "${OUTPUT_FILE}" != "${CONTEXT_DIR}/"* \
   && "${OUTPUT_FILE}" != "${DEBUG_DIR}/"* \
   && "${OUTPUT_FILE}" != "${ANALYSIS_DIR}/"* \
   && "${OUTPUT_FILE}" != "${AGENTS_TMP_DIR}/"* ]]; then
  log "Output file must stay inside an allowed temporary directory."
  log "Allowed context dir: ${CONTEXT_DIR}"
  log "Allowed debug dir: ${DEBUG_DIR}"
  log "Allowed analysis dir: ${ANALYSIS_DIR}"
  log "Allowed agents tmp dir: ${AGENTS_TMP_DIR}"
  log "Requested output file: ${OUTPUT_FILE}"
  log "No changes were made."
  exit 1
fi

"${SCRIPT_DIR}/agent_context_snapshot.sh"

mkdir -p "${CONTEXT_DIR}" "${DEBUG_DIR}" "${ANALYSIS_DIR}" "${AGENTS_TMP_DIR}" "$(dirname "${OUTPUT_FILE}")"

{
  printf '# Repo-Aware Prompt Input\n\n'
  printf 'Mode: readonly\n'
  printf 'CrawlerNest repo root: `%s`\n' "${REPO_ROOT}"
  printf 'Context snapshot path: `%s`\n' "${CONTEXT_SNAPSHOT}"
  printf 'Allowed output directories:\n'
  printf '%s\n' "- \`${CONTEXT_DIR}\`"
  printf '%s\n' "- \`${DEBUG_DIR}\`"
  printf '%s\n' "- \`${ANALYSIS_DIR}\`"
  printf '%s\n\n' "- \`${AGENTS_TMP_DIR}\`"
  printf 'Required boundary: analyze and recommend only; do not auto-fix, write memory, mutate pipelines, commit, open PRs, or modify CI.\n\n'

  if [[ -n "${NOTE_FILE}" ]]; then
    if [[ -f "${NOTE_FILE}" ]]; then
      printf '## User Log Or Note\n\n'
      printf 'Source: `%s`\n\n' "${NOTE_FILE}"
      printf '```text\n'
      sed -n '1,200p' "${NOTE_FILE}"
      printf '\n```\n\n'
    else
      printf '## User Log Or Note\n\n'
      printf '[missing] %s\n\n' "${NOTE_FILE}"
    fi
  fi

  printf '## Repository Context Snapshot\n\n'
  printf '```text\n'
  sed -n '1,240p' "${CONTEXT_SNAPSHOT}"
  printf '\n```\n'
} > "${PROMPT_INPUT}"

export CRAWLERNEST_REPO_ROOT="${REPO_ROOT}"
export CRAWLERNEST_AGENT_MODE="readonly"
export CRAWLERNEST_AGENT_CONTEXT_SNAPSHOT="${CONTEXT_SNAPSHOT}"
export CRAWLERNEST_AGENT_OUTPUT_DIR="${CONTEXT_DIR}"

log "Context snapshot: ${CONTEXT_SNAPSHOT}"
log "Prompt input: ${PROMPT_INPUT}"
log "Output file: ${OUTPUT_FILE}"
log "Mode: readonly"

cd "${AGENTS_REPO_ROOT}"
python3 "${PROMPT_GENERATOR}" "${PROMPT_INPUT}" "${OUTPUT_FILE}"
