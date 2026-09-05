#!/bin/sh
# Put the probe's configuration where dovecot reads it, build its mailbox tree, then become the
# IMAP server. The tree is made with mkdir because `doveadm` needs the auth socket of a server
# that is not listening yet. What each name below is for: docs/runbooks/email-imap.md.
set -eu

MAIL_UID=1000
MAIL_GID=1000
ROOT="$CORTEX_IMAP_PROBE_MAIL_ROOT/probe/Mail"

# `set -u` above already stops a container whose root never arrives. This covers the other way
# each can be wrong, a path the tmpfs is not mounted at: the image declares a volume at both
# paths, so docker would fill an unmounted one with a volume that outlives the container.
require_tmpfs() {
    if [ "$(stat -f -c %T "$1")" != tmpfs ]; then
        echo "$1 is not the tmpfs the compose file mounts; $2" >&2
        exit 1
    fi
}

require_tmpfs "$CORTEX_IMAP_PROBE_MAIL_ROOT" "the store would keep mail"
require_tmpfs "$CORTEX_IMAP_PROBE_CONFIG_ROOT" "every run would leave a volume behind"

# The configuration is copied onto the tmpfs from here rather than bound straight onto the path
# dovecot reads, because dovecot looks only in its compiled-in directory and nothing in the
# compose file can move it.
cp /probe.conf "$CORTEX_IMAP_PROBE_CONFIG_ROOT/dovecot.conf"

# An sdbox mailbox is a directory holding `dbox-Mails`; a directory without that child is what
# makes a listed name one that no SELECT opens.
mkdir -p "$ROOT/mailboxes/INBOX/dbox-Mails" \
    "$ROOT/mailboxes/Guarded/dbox-Mails" \
    "$ROOT/mailboxes/Parent/Child/dbox-Mails" \
    "$ROOT/mailboxes/Feigned/dbox-Mails" \
    "$ROOT/mailboxes/Feigned/Followed/dbox-Mails" \
    "$ROOT/mailboxes/Sealed/dbox-Mails"
# The ACL file goes inside the mailbox directory, where dovecot's vfile backend reads it; put
# anywhere else it is silently ignored.
printf 'owner l\n' > "$ROOT/mailboxes/Guarded/dbox-Mails/dovecot-acl"
printf 'V\t2\n\nGhost\nFeigned/Followed\n' > "$ROOT/subscriptions"
chown -R "$MAIL_UID:$MAIL_GID" "$CORTEX_IMAP_PROBE_MAIL_ROOT/probe"

# Poll for something the server does on its own, and stop the container when it never happens.
wait_until() {
    tries=0
    until "$@"; do
        tries=$((tries + 1))
        if [ "$tries" -gt 50 ]; then
            echo "gave up waiting for: $*" >&2
            exit 1
        fi
        sleep 0.2
    done
}

# A dbox message exists only once an index names it, and only a running server writes that index.
# So the server is started once on the container's own loopback, the message is saved through it,
# its file is shut, and the server is stopped again. The uid is 1 as the first message saved.
/usr/sbin/dovecot -o listen=127.0.0.1
wait_until test -S /run/dovecot/auth-userdb
printf 'From: sealed@example.com\r\nSubject: Sealed\r\n\r\nA message the mail process cannot open.\r\n' \
    | doveadm save -u probe -m Sealed
SEALED="$ROOT/mailboxes/Sealed/dbox-Mails/u.1"
chown root "$SEALED"
chmod 000 "$SEALED"
doveadm stop
wait_until test ! -e /run/dovecot/master.pid

exec /usr/sbin/dovecot -F
