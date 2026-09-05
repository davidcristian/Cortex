#!/bin/sh
# Put the probe's configuration where dovecot reads it, build its mailbox tree, then become the
# IMAP server (the container's entrypoint).
#
# Seven names a LIST returns, six of them mailboxes and one of them deliberately not, all in
# place before anything connects because the mail store is a tmpfs and starts empty every time.
# Between them they cover every answer a SELECT of a listed name can get, and one answer a FETCH
# can get:
#
#   INBOX            opens, so a run proves the login and the reader work before it asks about a
#                    refusal
#   Guarded          exists and is listed, and the ACL below leaves this user lookup rights only,
#                    so opening it is refused: the "there but shut" case no server this repo
#                    talks to can produce
#   Parent           listed \Noselect, and not a mailbox at all: it exists only as the parent of
#                    Parent/Child, and this server refuses to open it in the same words it refuses
#                    a name no mailbox has
#   Parent/Child     a real mailbox under that node, and it opens, which is what makes dropping
#                    the parent from an offered list lossless
#   Feigned          a real mailbox that opens, and the one name here a listing calls unselectable
#                    while lying about it. Its child below is subscribed and it is not, which is
#                    the state RFC 3501 makes an LSUB of `%` answer with \Noselect whatever the
#                    name really is, so this server sends the flag the ProtonMail Bridge sends in
#                    its ordinary LIST and then opens the name, which is the shape the flag filter
#                    exists to survive. Its ordinary LIST calls this one \HasChildren and nothing
#                    else, because there the flag and the refusal are one fact on this server.
#   Feigned/Followed the subscribed child that puts the flag on its parent, and a mailbox in its
#                    own right, so nothing about the pair depends on a name that cannot be opened
#   Sealed           a real mailbox that opens and holds one message whose dbox file the mail
#                    process cannot open (owned by root, mode 000), so a FETCH of it is the one
#                    read this server declines, answered with a tagged NO under the
#                    `imap_fetch_failure` probe.conf sets. It is the one name here finished after
#                    the server has run once, at the bottom, because a dbox message exists only
#                    once an index names it and only a server writes that index
#
# And an eighth name that no LIST returns, which is why it is written into a file rather than made
# as a directory:
#
#   Ghost            subscribed and not there, so a LIST that asks for subscriptions answers with
#                    it flagged \NonExistent, RFC 5258's newer spelling of "this is not a mailbox".
#                    It is the only way to make this server send that word: an ordinary LIST never
#                    carries it, and SUBSCRIBE of a name no mailbox has is itself refused here
#                    (`NO Mailbox doesn't exist: Ghost`), so the subscription cannot be arranged
#                    over the wire and the file is written directly. The format is dovecot's own,
#                    read back off a subscription it wrote itself: a `V<TAB>2` version line, an
#                    empty namespace-prefix line, then one name per line. The same file is what
#                    subscribes Feigned/Followed, for the same reason: it is written, not asked
#                    for, so the tree is whole before anything connects.
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
ROOT="$CORTEX_IMAP_PROBE_MAIL_ROOT/probe/Mail"

# Both roots are the compose file's, and a root that never arrives is already covered: `set -u`
# above stops the container here rather than building a tree at the filesystem root. This covers
# the other way each can be wrong, a path the tmpfs is not mounted at, which is the failure
# nothing else says out loud. The image declares a volume at both paths, so an unmounted one is
# not even the container's own writable layer: docker fills it with an anonymous volume that
# outlives the container. Under the mail root that is a store which answers every question the
# suite asks and keeps what a run leaves behind; under the configuration root it is a few
# kilobytes of the image's own settings left on the host after every single run, which is the
# promise the compose file makes and the one it could not keep.
require_tmpfs() {
    if [ "$(stat -f -c %T "$1")" != tmpfs ]; then
        echo "$1 is not the tmpfs the compose file mounts; $2" >&2
        exit 1
    fi
}

require_tmpfs "$CORTEX_IMAP_PROBE_MAIL_ROOT" "the store would keep mail"
require_tmpfs "$CORTEX_IMAP_PROBE_CONFIG_ROOT" "every run would leave a volume behind"

# The configuration is bound in beside this script and put on the tmpfs from here, rather than
# bound straight onto the path dovecot reads. That is deliberate: dovecot looks in its own
# compiled-in directory and nothing in the compose file can move it, so a configuration root
# written as any other path is a server reading the image's own settings, which the live suite
# fails loudly on, instead of a fixture that measures correctly and leaks a volume every run.
cp /probe.conf "$CORTEX_IMAP_PROBE_CONFIG_ROOT/dovecot.conf"

mkdir -p "$ROOT/mailboxes/INBOX/dbox-Mails" \
    "$ROOT/mailboxes/Guarded/dbox-Mails" \
    "$ROOT/mailboxes/Parent/Child/dbox-Mails" \
    "$ROOT/mailboxes/Feigned/dbox-Mails" \
    "$ROOT/mailboxes/Feigned/Followed/dbox-Mails" \
    "$ROOT/mailboxes/Sealed/dbox-Mails"
printf 'owner l\n' > "$ROOT/mailboxes/Guarded/dbox-Mails/dovecot-acl"
printf 'V\t2\n\nGhost\nFeigned/Followed\n' > "$ROOT/subscriptions"
chown -R "$MAIL_UID:$MAIL_GID" "$CORTEX_IMAP_PROBE_MAIL_ROOT/probe"

# Poll for something the server does on its own, and stop the container when it never happens,
# so a wait that would otherwise hang names itself in the logs instead.
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

# Sealed's message. A dbox message exists only once an index names it, and only a running server
# writes that index: `doveadm save` looks the account up over the auth socket the server creates,
# and fails with `connect(/run/dovecot/auth-userdb) failed` before one is listening, which is why
# this is not a mkdir like the rest. So the server is started once on the container's own
# loopback, where the published port cannot reach it, the message is saved through it, the file
# is shut, and the server is stopped again before the one below takes its place. The stop is the
# short gap the compose healthcheck's start period covers. The uid is 1 because it is the first
# message a fresh mailbox is given, and the file is named after the uid.
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
