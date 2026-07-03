#!/bin/sh
# Dump the database into the plug-and-play directory, once on start and then every
# CORTEX_DB_SYNC_INTERVAL_S seconds. The dump is written to a temporary file and moved into place
# so a reader never sees a partial file, and the previous dump is kept as cortex-previous.dump.
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
