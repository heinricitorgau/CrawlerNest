#!/usr/bin/env bash
# Backup/restore drill.
#   (no flag)   readonly-safe: prints the commands and checks the folders; dumps and restores nothing.
#   --execute   the real drill: scripts/release_snapshot.py drill -- dumps the live database into
#               .local/backups/, restores it into a scratch database, compares every table with live and
#               drops the scratch database. The live database is only read.
#   --execute --backup FILE   drills an existing backup instead of taking one.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${ROOT_DIR}/.local/backups"
SNAPSHOT_DIR="${ROOT_DIR}/.local/snapshots"
PGHOST="${CRAWLERNEST_PG_HOST:-127.0.0.1}"
PGPORT="${CRAWLERNEST_PG_PORT:-5432}"
PGDATABASE="${CRAWLERNEST_PG_DATABASE:-clawer}"
PGUSER="${CRAWLERNEST_PG_USER:-test}"
DRY_RUN=false
EXECUTE=false
BACKUP_FILE=""

usage() {
  cat <<USAGE
Usage: ./scripts/run_backup_restore_drill.sh [--dry-run] [--execute [--backup FILE]]

Prints pg_dump and pg_restore command previews and checks local backup/snapshot
readiness. It never deletes data and never runs restore.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --execute) EXECUTE=true ;;
    --backup) shift; BACKUP_FILE="${1:-}" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
  shift
done

if [[ "${EXECUTE}" == "true" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
  [[ -x "${PYTHON_BIN}" ]] || PYTHON_BIN="python3"
  export PGHOST PGPORT PGUSER PGDATABASE PGPASSWORD="${CRAWLERNEST_PG_PASSWORD:-${PGPASSWORD:-test}}"
  args=(drill)
  [[ -n "${BACKUP_FILE}" ]] && args+=(--backup "${BACKUP_FILE}")
  exec "${PYTHON_BIN}" "${ROOT_DIR}/scripts/release_snapshot.py" --pg-database "${PGDATABASE}" "${args[@]}"
fi

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
  warn "snapshot directory missing: .local/snapshots/"
fi

if [[ -d "${BACKUP_DIR}" ]]; then
  if [[ -w "${BACKUP_DIR}" ]]; then
    pass "backup directory writable: .local/backups/"
  else
    fail "backup directory is not writable: .local/backups/"
  fi
else
  warn "backup directory missing: .local/backups/"
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
echo "- To prove a backup restores, run with --execute (restores into a scratch database, never the live one)."

echo ""
echo "Summary: WARN=${warns} FAIL=${failures}"

if [[ "${failures}" -gt 0 ]]; then
  exit 1
fi
exit 0
