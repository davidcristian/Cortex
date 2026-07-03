#!/bin/sh
# Automated pg_dump sync into the plug-and-play database dir (ADR-0008 decision 7).
#
# Runs in the pg-backup sidecar (docker-compose.memory.yml): dumps immediately on start,
# then every CORTEX_DB_SYNC_INTERVAL_S seconds (default 6h). The dump is written to a temp
# file and mv'd into place so a reader never sees a partial file; the previous dump is kept
# as cortex-previous.dump (one-deep rotation). Credentials arrive via PGPASSWORD from the
# compose environment. A failed dump (e.g. Postgres restarting) exits the loop under
# `set -eu`; the service's restart policy brings it back. Failures are visible in
# `docker compose logs pg-backup`, never silently swallowed.
set -eu

: "${CORTEX_DB_SYNC_INTERVAL_S:=21600}"

while :; do
  pg_dump -h postgres -U cortex -d cortex -Fc -f /backup/cortex.dump.tmp
  if [ -f /backup/cortex.dump ]; then
    cp /backup/cortex.dump /backup/cortex-previous.dump
  fi
  mv /backup/cortex.dump.tmp /backup/cortex.dump
  echo "pg-backup: wrote /backup/cortex.dump ($(date -u +%Y-%m-%dT%H:%M:%SZ)); next in ${CORTEX_DB_SYNC_INTERVAL_S}s"
  sleep "${CORTEX_DB_SYNC_INTERVAL_S}"
done
