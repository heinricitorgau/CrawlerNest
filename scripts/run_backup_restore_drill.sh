#!/usr/bin/env bash
# Readonly-safe backup/restore drill. Prints commands; does not dump or restore.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${ROOT_DIR}/backups"
SNAPSHOT_DIR="${ROOT_DIR}/snapshots"
PGHOST="${CRAWLERNEST_PG_HOST:-127.0.0.1}"
PGPORT="${CRAWLERNEST_PG_PORT:-5432}"
PGDATABASE="${CRAWLERNEST_PG_DATABASE:-clawer}"
PGUSER="${CRAWLERNEST_PG_USER:-test}"
DRY_RUN=false

usage() {
  cat <<USAGE
Usage: ./scripts/run_backup_restore_drill.sh [--dry-run]

Prints pg_dump and pg_restore command previews and checks local backup/snapshot
readiness. It never deletes data and never runs restore.
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

failures=0
warns=0

pass() { echo "PASS $*"; }
warn() { echo "WARN $*"; warns=$((warns + 1)); }
fail() { echo "FAIL $*"; failures=$((failures + 1)); }

echo "[backup-drill] readonly-safe backup/restore drill"
echo "[backup-drill] dry_run=${DRY_RUN}"

if [[ -d "${SNAPSHOT_DIR}" ]]; then
  latest_snapshot="$(find "${SNAPSHOT_DIR}" -maxdepth 1 -type f -name '*.json' -print 2>/dev/null | sort | tail -n 1)"
  if [[ -n "${latest_snapshot}" ]]; then
    pass "snapshot exists: ${latest_snapshot#${ROOT_DIR}/}"
  else
    warn "snapshot directory exists but contains no JSON snapshots"
  fi
else
  warn "snapshot directory missing: snapshots/"
fi

if [[ -d "${BACKUP_DIR}" ]]; then
  if [[ -w "${BACKUP_DIR}" ]]; then
    pass "backup directory writable: backups/"
  else
    fail "backup directory is not writable: backups/"
  fi
else
  warn "backup directory missing: backups/"
fi

timestamp="$(date -u +"%Y%m%d_%H%M%S")"
backup_file="${BACKUP_DIR}/crawlernest_${PGDATABASE}_${timestamp}.dump"

echo ""
echo "Backup command preview:"
printf 'PGPASSWORD="$CRAWLERNEST_PG_PASSWORD" pg_dump --format=custom --host=%q --port=%q --username=%q --dbname=%q --file=%q\n' \
  "${PGHOST}" "${PGPORT}" "${PGUSER}" "${PGDATABASE}" "${backup_file}"

echo ""
echo "Restore command preview:"
printf 'PGPASSWORD="$CRAWLERNEST_PG_PASSWORD" pg_restore --clean --if-exists --host=%q --port=%q --username=%q --dbname=%q %q\n' \
  "${PGHOST}" "${PGPORT}" "${PGUSER}" "${PGDATABASE}" "${backup_file}"

echo ""
echo "Safety notes:"
echo "- This drill did not run pg_dump."
echo "- This drill did not run pg_restore."
echo "- Restore remains a manual, destructive operation and must be reviewed."

echo ""
echo "Summary: WARN=${warns} FAIL=${failures}"

if [[ "${failures}" -gt 0 ]]; then
  exit 1
fi
exit 0
