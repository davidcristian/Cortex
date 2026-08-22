#!/bin/sh
set -eu

MAIL_UID=1000
MAIL_GID=1000
ROOT=/srv/mail/probe/Mail

mkdir -p "$ROOT/mailboxes/INBOX/dbox-Mails" \
    "$ROOT/mailboxes/Guarded/dbox-Mails" \
    "$ROOT/mailboxes/Parent/Child/dbox-Mails"
printf 'owner l\n' > "$ROOT/mailboxes/Guarded/dbox-Mails/dovecot-acl"
printf 'V\t2\n\nGhost\n' > "$ROOT/subscriptions"
chown -R "$MAIL_UID:$MAIL_GID" /srv/mail/probe

exec /usr/sbin/dovecot -F
