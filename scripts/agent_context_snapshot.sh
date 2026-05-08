#!/usr/bin/env bash
# Build a readonly repository operational context snapshot for agent prompts.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/tmp/agent-context"
OUTPUT_FILE="${OUTPUT_DIR}/context_snapshot.md"

latest_file() {
  local pattern="$1"
  find "${REPO_ROOT}" \
    -path "${REPO_ROOT}/.git" -prune -o \
    -type f -path "${REPO_ROOT}/${pattern}" -print 2>/dev/null \
    | sort \
    | tail -n 1
}

print_file_or_missing() {
  local label="$1"
  local file="$2"
  local max_lines="${3:-120}"

  if [[ -n "${file}" && -f "${file}" ]]; then
    printf 'Source: `%s`\n\n' "${file#${REPO_ROOT}/}"
    printf '```text\n'
    sed -n "1,${max_lines}p" "${file}"
    printf '\n```\n'
  else
    printf '[missing] %s\n' "${label}"
  fi
}

mkdir -p "${OUTPUT_DIR}"

BRANCH="$(git -C "${REPO_ROOT}" branch --show-current 2>/dev/null || true)"
if [[ -z "${BRANCH}" ]]; then
  BRANCH="$(git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
fi
if [[ -z "${BRANCH}" ]]; then
  BRANCH="[missing]"
fi

LATEST_COMMIT="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || true)"
if [[ -z "${LATEST_COMMIT}" ]]; then
  LATEST_COMMIT="[missing]"
fi

GIT_STATUS="$(git -C "${REPO_ROOT}" status --short 2>/dev/null || true)"
if [[ -z "${GIT_STATUS}" ]]; then
  GIT_STATUS="(clean)"
fi

SMOKE_SUMMARY="$(latest_file "reports/*smoke*.md")"
if [[ -z "${SMOKE_SUMMARY}" ]]; then
  SMOKE_SUMMARY="$(latest_file "reports/*smoke*.txt")"
fi
if [[ -z "${SMOKE_SUMMARY}" ]]; then
  SMOKE_SUMMARY="$(latest_file "logs/*smoke*.log")"
fi

FAILURE_SUMMARY="$(latest_file "reports/latest_failure_summary.md")"
if [[ -z "${FAILURE_SUMMARY}" ]]; then
  FAILURE_SUMMARY="$(latest_file "reports/*failure*summary*.md")"
fi

DIAGNOSTICS_SNAPSHOT="$(latest_file "snapshots/latest_status.json")"
if [[ -z "${DIAGNOSTICS_SNAPSHOT}" ]]; then
  DIAGNOSTICS_SNAPSHOT="$(latest_file "snapshots/system_snapshot_*.json")"
fi

FRESHNESS_SNAPSHOT="$(latest_file "snapshots/*freshness*.json")"
if [[ -z "${FRESHNESS_SNAPSHOT}" ]]; then
  FRESHNESS_SNAPSHOT="${DIAGNOSTICS_SNAPSHOT}"
fi

REGRESSION_SUMMARY="$(latest_file "reports/*regression*.md")"
if [[ -z "${REGRESSION_SUMMARY}" ]]; then
  REGRESSION_SUMMARY="$(latest_file "reports/*regression*.json")"
fi
if [[ -z "${REGRESSION_SUMMARY}" ]]; then
  REGRESSION_SUMMARY="${FAILURE_SUMMARY}"
fi

{
  printf '# CrawlerNest Agent Context Snapshot\n\n'
  printf 'Generated: `%s`\n\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  printf '## Repository State\n\n'
  printf '%s\n' "- Branch: \`${BRANCH}\`"
  printf '%s\n' "- Latest commit: \`${LATEST_COMMIT}\`"
  printf '%s\n\n' "- Snapshot path: \`${OUTPUT_FILE#${REPO_ROOT}/}\`"

  printf '## Changed Files\n\n'
  printf '```text\n%s\n```\n\n' "${GIT_STATUS}"

  printf '## Latest Smoke Results\n\n'
  print_file_or_missing "latest smoke summary" "${SMOKE_SUMMARY}" 80
  printf '\n'

  printf '## Latest Diagnostics\n\n'
  print_file_or_missing "latest diagnostics snapshot" "${DIAGNOSTICS_SNAPSHOT}" 120
  printf '\n'

  printf '## Latest Failures\n\n'
  print_file_or_missing "latest failure summary" "${FAILURE_SUMMARY}" 120
  printf '\n'

  printf '## Latest Freshness\n\n'
  print_file_or_missing "latest freshness snapshot" "${FRESHNESS_SNAPSHOT}" 120
  printf '\n'

  printf '## Latest Regression Summary\n\n'
  print_file_or_missing "latest regression summary" "${REGRESSION_SUMMARY}" 120
} > "${OUTPUT_FILE}"

printf '[agent-context] Context snapshot written to %s\n' "${OUTPUT_FILE}"
