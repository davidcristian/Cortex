#!/bin/sh
# Build the probe's mailbox tree, then become the IMAP server (the container's entrypoint).
#
# Six names a LIST returns, five of them mailboxes and one of them deliberately not, all in
# place before anything connects because the mail store is a tmpfs and starts empty every time.
# Between them they cover every answer a SELECT of a listed name can get:
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
#
# And a seventh name that no LIST returns, which is why it is written into a file rather than made
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

# The mail root is the compose file's, and dovecot resolves the account's home out of the same
# variable, so the store, this tree and that home are one spelling rather than three. A root that
# never arrives is already covered: `set -u` above stops the container here rather than building a
# tree at the filesystem root. This covers the other way it can be wrong, a root the tmpfs is not
# mounted at. Such a store answers every question the suite asks and keeps what a run leaves
# behind, which is the one property this fixture claims for itself and the only one whose loss
# nothing else would say out loud, so it is checked rather than trusted. The image declares a
# volume at the path the compose file mounts, so an unmounted root is not even the container's own
# writable layer: docker fills it with an anonymous volume that outlives the container.
if [ "$(stat -f -c %T "$CORTEX_IMAP_PROBE_MAIL_ROOT")" != tmpfs ]; then
    echo "the mail root is not the tmpfs the compose file mounts; the store would keep mail" >&2
    exit 1
fi

mkdir -p "$ROOT/mailboxes/INBOX/dbox-Mails" \
    "$ROOT/mailboxes/Guarded/dbox-Mails" \
    "$ROOT/mailboxes/Parent/Child/dbox-Mails" \
    "$ROOT/mailboxes/Feigned/dbox-Mails" \
    "$ROOT/mailboxes/Feigned/Followed/dbox-Mails"
printf 'owner l\n' > "$ROOT/mailboxes/Guarded/dbox-Mails/dovecot-acl"
printf 'V\t2\n\nGhost\nFeigned/Followed\n' > "$ROOT/subscriptions"
chown -R "$MAIL_UID:$MAIL_GID" "$CORTEX_IMAP_PROBE_MAIL_ROOT/probe"

exec /usr/sbin/dovecot -F
