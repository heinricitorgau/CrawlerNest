#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT_FILE="${SNAPSHOT_FILE:-${ROOT_DIR}/releases/v0.2-2026-snapshot/clawer-2026-09-04-release-freeze.dump}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-test}"
PGPASSWORD="${PGPASSWORD:-test}"
PGDATABASE="${PGDATABASE:-clawer}"

if [[ ! -f "${SNAPSHOT_FILE}" ]]; then
  echo "Snapshot not found: ${SNAPSHOT_FILE}" >&2
  exit 1
fi

export PGPASSWORD
for attempt in $(seq 1 30); do
  if pg_isready -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" >/dev/null 2>&1; then
    break
  fi
  if [[ "${attempt}" == "30" ]]; then
    echo "PostgreSQL did not become ready at ${PGHOST}:${PGPORT}/${PGDATABASE}." >&2
    exit 1
  fi
  sleep 2
done

echo "Restoring ${SNAPSHOT_FILE} into ${PGDATABASE}..."
pg_restore -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" \
  --no-owner --no-acl --exit-on-error "${SNAPSHOT_FILE}"

echo "Verifying frozen 2026 data..."
psql -X -v ON_ERROR_STOP=1 -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" <<'SQL'
DO $$
DECLARE actual bigint;
BEGIN
  SELECT count(*) INTO actual FROM analytics.aggregated_rankings WHERE ranking_year = 2026;
  IF actual <> 10125 THEN RAISE EXCEPTION 'Expected 10125 aggregated rows, got %', actual; END IF;
  SELECT count(*) INTO actual FROM warehouse.ranking_record WHERE ranking_year = 2026;
  IF actual <> 12005 THEN RAISE EXCEPTION 'Expected 12005 ranking records, got %', actual; END IF;
  SELECT count(*) INTO actual FROM analytics.v_ml_predictions_latest;
  IF actual = 0 THEN RAISE EXCEPTION 'analytics.v_ml_predictions_latest is empty'; END IF;
END $$;

DO $$
DECLARE actual bigint;
BEGIN
  SELECT count(*) INTO actual
  FROM warehouse.ranking_record rr
  JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
  WHERE rr.ranking_year = 2026 AND rs.source_code = 'QS';
  IF actual <> 9530 THEN RAISE EXCEPTION 'Expected 9530 QS rows, got %', actual; END IF;
  SELECT count(*) INTO actual
  FROM warehouse.ranking_record rr
  JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
  WHERE rr.ranking_year = 2026 AND rs.source_code = 'THE';
  IF actual <> 1637 THEN RAISE EXCEPTION 'Expected 1637 THE rows, got %', actual; END IF;
  SELECT count(*) INTO actual
  FROM warehouse.ranking_record rr
  JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
  WHERE rr.ranking_year = 2026 AND rs.source_code = 'ARWU';
  IF actual <> 838 THEN RAISE EXCEPTION 'Expected 838 ARWU rows, got %', actual; END IF;
END $$;

DO $$
DECLARE actual bigint;
BEGIN
  SELECT count(*) INTO actual FROM analytics.aggregated_rankings WHERE ranking_year = 2026 AND universe_type = 'global';
  IF actual <> 2098 THEN RAISE EXCEPTION 'Expected 2098 global rows, got %', actual; END IF;
  SELECT count(*) INTO actual FROM analytics.aggregated_rankings WHERE ranking_year = 2026 AND universe_type = 'region';
  IF actual <> 1629 THEN RAISE EXCEPTION 'Expected 1629 region rows, got %', actual; END IF;
  SELECT count(*) INTO actual FROM analytics.aggregated_rankings WHERE ranking_year = 2026 AND universe_type = 'regional';
  IF actual <> 3198 THEN RAISE EXCEPTION 'Expected 3198 regional rows, got %', actual; END IF;
  SELECT count(*) INTO actual FROM analytics.aggregated_rankings WHERE ranking_year = 2026 AND universe_type = 'special';
  IF actual <> 2074 THEN RAISE EXCEPTION 'Expected 2074 special rows, got %', actual; END IF;
  SELECT count(*) INTO actual FROM analytics.aggregated_rankings WHERE ranking_year = 2026 AND universe_type = 'subject';
  IF actual <> 1126 THEN RAISE EXCEPTION 'Expected 1126 subject rows, got %', actual; END IF;
END $$;
SQL

if [[ -n "${API_BASE_URL:-}" ]]; then
  echo "Verifying API endpoints at ${API_BASE_URL}..."
  curl --fail --silent --show-error "${API_BASE_URL}/api/v1/rankings?page=1&pageSize=1" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; assert d["items"][0]["rankingYear"] == 2026; assert d["items"][0]["sourceCount"] == 3; assert d["metadata"]["totalCount"] == 2098'
  curl --fail --silent --show-error "${API_BASE_URL}/api/v1/analytics/ranking-trends" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; assert d["available_years"] == [2026]; assert d["single_year_only"] is True'
fi

echo "Release snapshot restore and verification passed."