#!/bin/sh
# Build the probe's mailbox tree, then become the IMAP server (the container's entrypoint).
#
# Four names a LIST returns, three of them mailboxes and one of them deliberately not, all in
# place before anything connects because the mail store is a tmpfs and starts empty every time.
# Between them they cover every answer a SELECT of a listed name can get:
#
#   INBOX         opens, so a run proves the login and the reader work before it asks about a
#                 refusal
#   Guarded       exists and is listed, and the ACL below leaves this user lookup rights only,
#                 so opening it is refused: the "there but shut" case no server this repo
#                 talks to can produce
#   Parent        listed \Noselect, and not a mailbox at all: it exists only as the parent of
#                 Parent/Child, and this server refuses to open it in the same words it refuses
#                 a name no mailbox has
#   Parent/Child  a real mailbox under that node, and it opens, which is what makes dropping
#                 the parent from an offered list lossless
#
# The tree is made with mkdir rather than with `doveadm`, which would need the auth socket of a
# server that is not listening yet. An sdbox mailbox IS a directory holding `dbox-Mails`, and
# dovecot writes its own indexes into one on first use; a directory without that child is
# exactly what makes `Parent` unselectable. The ACL file goes inside the mailbox directory (the
# path `doveadm acl debug` prints), not beside it: dovecot's vfile backend reads it from there
# and silently sees no ACL otherwise.
set -eu

MAIL_UID=1000
MAIL_GID=1000
ROOT=/srv/mail/probe/Mail

mkdir -p "$ROOT/mailboxes/INBOX/dbox-Mails" \
    "$ROOT/mailboxes/Guarded/dbox-Mails" \
    "$ROOT/mailboxes/Parent/Child/dbox-Mails"
printf 'owner l\n' > "$ROOT/mailboxes/Guarded/dbox-Mails/dovecot-acl"
chown -R "$MAIL_UID:$MAIL_GID" /srv/mail/probe

exec /usr/sbin/dovecot -F
