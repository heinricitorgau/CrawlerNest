#!/usr/bin/env bash
# Safely clean old generated operational artifacts inside this repository.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=false

usage() {
  cat <<USAGE
Usage: ./scripts/cleanup_old_artifacts.sh [--dry-run]

Retention:
  snapshots/          keep latest 30 files
  reports/            keep latest 30 files
  backups/            keep latest 30 files
  tmp/agent-context/  keep latest 20 files
  tmp/agent-debug/    keep latest 20 files
  tmp/agent-analysis/ keep latest 20 files
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
  shift
done

is_safe_dir() {
  local target="$1"
  [[ -n "${target}" ]] || return 1
  [[ "${target}" != "/" ]] || return 1
  [[ "${target}" != *"*"* ]] || return 1
  [[ "${target}" != *"?"* ]] || return 1
  [[ "${target}" == "${ROOT_DIR}"/* ]] || return 1
}

cleanup_dir() {
  local rel_dir="$1"
  local keep="$2"
  local dir="${ROOT_DIR}/${rel_dir}"

  if ! is_safe_dir "${dir}"; then
    echo "FAIL unsafe cleanup path rejected: ${dir}"
    return 1
  fi

  if [[ ! -d "${dir}" ]]; then
    echo "SKIP ${rel_dir} [missing]"
    return 0
  fi

  echo "CHECK ${rel_dir} keep latest ${keep}"

  mapfile -d '' files < <(
    find "${dir}" -maxdepth 1 -type f -printf '%T@ %p\0' 2>/dev/null \
      | sort -z -rn \
      | cut -z -d' ' -f2-
  )

  local idx=0
  local removed=0
  local file
  for file in "${files[@]}"; do
    idx=$((idx + 1))
    if (( idx <= keep )); then
      continue
    fi

    if ! is_safe_dir "$(dirname "${file}")"; then
      echo "FAIL unsafe file parent rejected: ${file}"
      return 1
    fi

    if "${DRY_RUN}"; then
      echo "DRY-RUN remove ${file#${ROOT_DIR}/}"
    else
      rm -f -- "${file}"
      echo "REMOVE ${file#${ROOT_DIR}/}"
    fi
    removed=$((removed + 1))
  done

  echo "OK ${rel_dir} candidates=${#files[@]} removed=${removed}"
}

cleanup_dir "snapshots" 30
cleanup_dir "reports" 30
cleanup_dir "backups" 30
cleanup_dir "tmp/agent-context" 20
cleanup_dir "tmp/agent-debug" 20
cleanup_dir "tmp/agent-analysis" 20
