#!/bin/sh
set -eu

MAIL_UID=1000
MAIL_GID=1000
ROOT="$CORTEX_IMAP_PROBE_MAIL_ROOT/probe/Mail"

require_tmpfs() {
    if [ "$(stat -f -c %T "$1")" != tmpfs ]; then
        echo "$1 is not the tmpfs the compose file mounts; $2" >&2
        exit 1
    fi
}

require_tmpfs "$CORTEX_IMAP_PROBE_MAIL_ROOT" "the store would keep mail"
require_tmpfs "$CORTEX_IMAP_PROBE_CONFIG_ROOT" "every run would leave a volume behind"

cp /probe.conf "$CORTEX_IMAP_PROBE_CONFIG_ROOT/dovecot.conf"

mkdir -p "$ROOT/mailboxes/INBOX/dbox-Mails" \
    "$ROOT/mailboxes/Guarded/dbox-Mails" \
    "$ROOT/mailboxes/Parent/Child/dbox-Mails" \
    "$ROOT/mailboxes/Feigned/dbox-Mails" \
    "$ROOT/mailboxes/Feigned/Followed/dbox-Mails"
printf 'owner l\n' > "$ROOT/mailboxes/Guarded/dbox-Mails/dovecot-acl"
printf 'V\t2\n\nGhost\nFeigned/Followed\n' > "$ROOT/subscriptions"
chown -R "$MAIL_UID:$MAIL_GID" "$CORTEX_IMAP_PROBE_MAIL_ROOT/probe"

exec /usr/sbin/dovecot -F
