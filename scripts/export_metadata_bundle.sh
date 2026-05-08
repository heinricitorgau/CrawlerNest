#!/usr/bin/env bash
# Export a metadata bundle containing diagnostics artifacts (no DB dump).
#
# Bundles:
#   - snapshots/*.json
#   - reports/*.md
#   - logs/daily_pipeline_*.log (last 7 days)
#
# Output: backups/metadata_bundle_YYYYMMDD_HHMMSS.tar.gz
#
# Usage:
#   ./scripts/export_metadata_bundle.sh [--output-dir /custom/path]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OUTPUT_DIR="${ROOT_DIR}/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BUNDLE_NAME="metadata_bundle_${TIMESTAMP}.tar.gz"

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir) OUTPUT_DIR="$2"; shift ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

mkdir -p "${OUTPUT_DIR}"

# ── Collect files to bundle ───────────────────────────────────────────────────
BUNDLE_PATH="${OUTPUT_DIR}/${BUNDLE_NAME}"
STAGING_MANIFEST="${OUTPUT_DIR}/.bundle_manifest_${TIMESTAMP}.txt"
: > "${STAGING_MANIFEST}"

add_glob() {
  local pattern="$1"
  # shellcheck disable=SC2086
  for f in ${pattern}; do
    [[ -f "${f}" ]] && echo "${f}" >> "${STAGING_MANIFEST}"
  done
}

add_glob "${ROOT_DIR}/snapshots/*.json"
add_glob "${ROOT_DIR}/reports/*.md"

# Only recent pipeline logs (last 7 days by filename YYYYMMDD suffix)
CUTOFF="$(date -d '7 days ago' +%Y%m%d 2>/dev/null || date -v-7d +%Y%m%d 2>/dev/null || echo "00000000")"
for f in "${ROOT_DIR}"/logs/daily_pipeline_*.log; do
  [[ -f "${f}" ]] || continue
  # Extract YYYYMMDD from filename
  basename_f="$(basename "${f}")"
  date_part="${basename_f#daily_pipeline_}"
  date_part="${date_part%.log}"
  if [[ "${date_part}" =~ ^[0-9]{8}$ ]] && [[ "${date_part}" -ge "${CUTOFF}" ]]; then
    echo "${f}" >> "${STAGING_MANIFEST}"
  fi
done

FILE_COUNT="$(wc -l < "${STAGING_MANIFEST}" | tr -d ' ')"
echo "[bundle] found ${FILE_COUNT} artifact(s) to bundle"

if [[ "${FILE_COUNT}" -eq 0 ]]; then
  echo "[bundle] nothing to bundle — run the pipeline first"
  rm -f "${STAGING_MANIFEST}"
  exit 0
fi

# ── Create tar.gz ─────────────────────────────────────────────────────────────
# Use -T for file list; paths are relative to ROOT_DIR
(
  cd "${ROOT_DIR}"
  # Rewrite manifest paths to be relative
  sed "s|${ROOT_DIR}/||g" "${STAGING_MANIFEST}" | \
    tar -czf "${BUNDLE_PATH}" -T -
)

rm -f "${STAGING_MANIFEST}"

BUNDLE_SIZE="$(du -sh "${BUNDLE_PATH}" | cut -f1)"
echo "[bundle] created: ${BUNDLE_PATH} (${BUNDLE_SIZE})"

# ── Retention: keep only the last 30 bundles ──────────────────────────────────
mapfile -t all_bundles < <(ls -1t "${OUTPUT_DIR}"/metadata_bundle_*.tar.gz 2>/dev/null)
if [[ ${#all_bundles[@]} -gt 30 ]]; then
  for old in "${all_bundles[@]:30}"; do
    echo "[bundle] removing old bundle: $(basename "${old}")"
    rm -f "${old}"
  done
fi

echo "[bundle] done. Output: ${BUNDLE_PATH}"
