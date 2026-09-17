#!/usr/bin/env bash
# ============================================================================
# PROJECT KKP — inisialisasi database dari kondisi kosong
#
#   database/scripts/init_db.sh [socket]
#
# Langkah:
#   1) (opsional) drop database bila ingin build bersih: --drop
#   2) apply schema.sql
#   3) apply seluruh seeds/*.sql (idempotent)
#
# Contoh:
#   bash database/scripts/init_db.sh                 # pakai socket default
#   bash database/scripts/init_db.sh --drop          # rebuild bersih
# ============================================================================
set -euo pipefail

MYSQL_BIN="${MYSQL_BIN:-/Users/Shared/DBngin/mysql/8.0.33/bin/mysql}"
MYSQL_SOCK="${MYSQL_SOCK:-/tmp/mysql_3306.sock}"
MYSQL_USER="${MYSQL_USER:-root}"
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DROP_MODE=""

if [[ "${1:-}" == "--drop" ]]; then
    DROP_MODE="1"
fi

if [[ ! -x "${MYSQL_BIN}" ]]; then
    echo "ERROR: mysql client tidak ditemukan di ${MYSQL_BIN}" >&2
    exit 1
fi

run_sql() {
    "${MYSQL_BIN}" -u"${MYSQL_USER}" --socket="${MYSQL_SOCK}" "$@"
}

if [[ -n "${DROP_MODE}" ]]; then
    echo "[init] drop database kkp_exim_platform (build bersih)..."
    # mysql -e "DROP DATABASE IF EXISTS kkp_exim_platform;"
    "${MYSQL_BIN}" -u"${MYSQL_USER}" --socket="${MYSQL_SOCK}" \
        -e "DROP DATABASE IF EXISTS kkp_exim_platform;" \
        || { echo "ERROR: gagal drop database" >&2; exit 1; }
fi

echo "[init] apply schema.sql ..."
run_sql < "${PROJECT_DIR}/database/schema.sql" \
    || { echo "ERROR: apply schema.sql gagal" >&2; exit 1; }

for f in "${PROJECT_DIR}"/database/seeds/*.sql; do
    echo "[init] seed $(basename "$f") ..."
    run_sql < "$f" || { echo "ERROR: seed $f gagal" >&2; exit 1; }
done

echo "[init] verifikasi tabel:"
run_sql -e "SELECT table_name AS 'tabel', table_rows AS 'estimasi_baris' FROM information_schema.tables WHERE table_schema='kkp_exim_platform' ORDER BY table_name;"

echo "[init] SUKSES"