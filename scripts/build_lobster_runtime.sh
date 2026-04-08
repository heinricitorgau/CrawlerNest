#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_ROOT="${REPO_ROOT}/crawlernest"
RUNTIME_ROOT="${REPO_ROOT}/lobster-01"

WITH_DATA=false
MINIMAL=false

usage() {
  cat <<'EOF'
Usage:
  scripts/build_lobster_runtime.sh [--with-data] [--minimal]

Options:
  --with-data   Include crawlernest/crawlernest-kb contents in the runtime package.
  --minimal     Build a lean package without copied data payloads and without prepared logs/.
  -h, --help    Show this help text.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-data)
      WITH_DATA=true
      shift
      ;;
    --minimal)
      MINIMAL=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[build] Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "${MINIMAL}" == true ]]; then
  WITH_DATA=false
fi

copy_dir() {
  local src="$1"
  local dest_parent="$2"

  if [[ ! -e "${src}" ]]; then
    echo "[build] Missing source path: ${src}" >&2
    exit 1
  fi

  mkdir -p "${dest_parent}"
  cp -R "${src}" "${dest_parent}/"
}

clean_runtime() {
  echo "[build] Cleaning previous runtime: ${RUNTIME_ROOT}"
  rm -rf \
    "${RUNTIME_ROOT}/crawlernest" \
    "${RUNTIME_ROOT}/logs" \
    "${RUNTIME_ROOT}/requirements.txt"
}

prepare_layout() {
  echo "[build] Preparing runtime layout..."
  mkdir -p "${RUNTIME_ROOT}"
  mkdir -p "${RUNTIME_ROOT}/crawlernest"

  if [[ "${MINIMAL}" != true ]]; then
    mkdir -p "${RUNTIME_ROOT}/logs"
    : > "${RUNTIME_ROOT}/logs/.gitkeep"
  fi
}

copy_runtime_templates() {
  echo "[build] Using runtime assets already stored in ${RUNTIME_ROOT}..."
  cp "${REPO_ROOT}/requirements.txt" "${RUNTIME_ROOT}/requirements.txt"
  chmod +x "${RUNTIME_ROOT}/run_lobster.sh"
}

copy_pipeline_sources() {
  echo "[build] Copying pipeline sources..."

  local -a required_paths=(
    "run_pipeline.py"
    "pipeline"
    "crawlernest-core"
    "crawlernest-db-writer"
    "crawlernest-extractors"
    "crawlernest-jobs"
    "crawlernest-schema"
    "crawlernest-normalization"
    "crawlernest-normalization-py"
  )

  local path
  for path in "${required_paths[@]}"; do
    copy_dir "${SOURCE_ROOT}/${path}" "${RUNTIME_ROOT}/crawlernest"
  done
}

prepare_kb() {
  echo "[build] Preparing knowledge-base runtime directories..."

  if [[ "${WITH_DATA}" == true ]]; then
    echo "[build] Including crawlernest-kb payloads..."
    copy_dir "${SOURCE_ROOT}/crawlernest-kb" "${RUNTIME_ROOT}/crawlernest"
  else
    mkdir -p "${RUNTIME_ROOT}/crawlernest/crawlernest-kb/databases"
    mkdir -p "${RUNTIME_ROOT}/crawlernest/crawlernest-kb/qs_universes"
    : > "${RUNTIME_ROOT}/crawlernest/crawlernest-kb/databases/.gitkeep"
    : > "${RUNTIME_ROOT}/crawlernest/crawlernest-kb/qs_universes/.gitkeep"
  fi
}

prune_dev_artifacts() {
  echo "[build] Removing development-only artifacts..."

  find "${RUNTIME_ROOT}" \
    \( -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" \) \) -prune -exec rm -rf {} +

  find "${RUNTIME_ROOT}" \
    -type f \( -name "*.pyc" -o -name ".DS_Store" -o -name "*.log" \) -delete
}

print_summary() {
  echo "[build] Runtime package ready."
  echo "[build] Output: ${RUNTIME_ROOT}"
  echo "[build] Flags : with_data=${WITH_DATA} minimal=${MINIMAL}"
}

main() {
  clean_runtime
  prepare_layout
  copy_runtime_templates
  copy_pipeline_sources
  prepare_kb
  prune_dev_artifacts
  print_summary
}

main "$@"
