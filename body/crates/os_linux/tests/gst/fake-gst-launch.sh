#!/bin/sh
# Stands in for gst-launch-1.0: the node in its fourth argument picks what it does.
case "$4" in
path=1) exec cat ;;
path=2) printf 'pipewiresrc: no stream\n' >&2; exit 3 ;;
path=3) printf 'not a picture' ;;
path=4) exec sleep 30 ;;
*) printf '\211PNG\r\n\032\n%s\n' "$LC_ALL"; printf '%s\n' "$@" ;;
esac
