#!/bin/sh
# Print the host's IANA zone, such as Europe/Berlin, or nothing when no source names one.
# The recipes that start the stack pass it to the brain as CORTEX_SCHEDULE_TZ when that is unset.
zone=$(timedatectl show -p Timezone --value 2>/dev/null) || zone=""
if [ -z "$zone" ] && [ -r /etc/timezone ]; then
  zone=$(head -n 1 /etc/timezone)
fi
if [ -z "$zone" ]; then
  link=$(readlink /etc/localtime 2>/dev/null) || link=""
  case "$link" in
    */zoneinfo/*) zone=${link#*/zoneinfo/} ;;
  esac
fi
printf '%s' "$zone"
