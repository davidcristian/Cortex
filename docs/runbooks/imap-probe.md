# Runbook: the local IMAP probe server

A `NO` to `SELECT` covers two facts, a mailbox that does not exist and a mailbox that does and
cannot be opened, and the ProtonMail Bridge produces only the first. This runbook is the second
server, a Dovecot run locally for the purpose, and what it answers. The Bridge half is in
[email-imap.md](email-imap.md) and every answer either server gives is recorded in
[IMAP server answers](../readings/imap-server-answers.md).

The server's ACL plugin can leave a mailbox listed, real and shut
([ADR-0057](../adr/ADR-0057-imap-probe-server.md)). It holds one message, sealed so that the mail
process cannot read it, checks no password, publishes on loopback only, and has nothing to do with
the brain stack:

```
just up-imap-probe
just email-folder-probe
just down-imap-probe
```

Its LIST returns seven names, six of them mailboxes (`INBOX`, `Parent/Child`, `Feigned`,
`Feigned/Followed` and `Sealed`, which open, and `Guarded`, which does not) and one a `\Noselect`
node that is not a mailbox at all (`Parent`). An eighth name, `Ghost`, is subscribed and not
there, which no LIST returns and which exists only to make the server send `\NonExistent`. What
each is for is written in `docker/dovecot/probe-mailboxes.sh`, which builds them, and all eight
are named a second time by `packages/email/tests/test_imap_probe_live.py`, which
`scripts/crosscheck.py` holds together.

The mail store is a tmpfs, so every start builds the tree again from nothing, and the path it sits
at is written once in `docker/docker-compose.imap-probe.yml` and handed to the container as
`CORTEX_IMAP_PROBE_MAIL_ROOT`, which the entrypoint reads and dovecot expands with `%{env:...}`.
The configuration directory is a tmpfs too, handed over as `CORTEX_IMAP_PROBE_CONFIG_ROOT`, because
the image declares a volume there as well and a container with nothing mounted at it leaves an
anonymous volume behind on every run; the conf is bound in at `/probe.conf` and copied onto that
mount by the entrypoint. So a full `up` and `down` leaves `docker volume ls` exactly as it found
it, which is worth checking after a Dovecot bump.

Three ways this fixture fails to start, all by design and all naming themselves in `docker compose
logs`: `is not the tmpfs the compose file mounts` means one of the two mounts went missing,
`parameter not set` means the variable behind it never arrived, and `gave up waiting for:` means
the first start of the server never produced its auth socket or its stop never finished. `just
up-imap-probe` reports each as a container that exited rather than as a stack that came up. The
recipe reaches the server at the published port when that answers and at the container's own
address when it does not.

Four things the answers show, all tabulated in [IMAP server
answers](../readings/imap-server-answers.md). The refusal for a mailbox that is there and shut uses
none of the words that prove a folder missing, which is the assumption the whole classification
rests on. The refusal for a missing mailbox shares no word with the Bridge's, so both phrases are
read and neither server sends a response code to read instead. The refusal for a name no mailbox
could have says nothing about a mailbox at all, so it is read off RFC 5530's `[CANNOT]` instead.
And this server refuses a listed `\Noselect` node exactly as it refuses a name no mailbox has,
where the Bridge's own `\Noselect` parents open; since the refusal cannot tell the two apart,
`list_folders` reads the LIST attributes imap-tools already provides beside each name and opens
anything flagged `\Noselect` or `\NonExistent` before deciding, dropping it only when the refusal
is one of the two that prove a folder missing. So `Parent` goes, `Parent/Child` is listed in its
own right, and `Guarded` stays because its refusal says the mailbox is shut.

`Sealed` is the one read this server declines. It holds one message whose dbox file the entrypoint
makes unreadable to the mail process after saving it through a first, loopback-only start of the
server, and `docker/dovecot/probe.conf` sets `imap_fetch_failure = no-after`, so the FETCH is
answered with a tagged `NO` on a connection that stays open rather than with Dovecot's default `*
BYE` and a dropped connection. The adapter reads only a uid no message has as a message that is not
there; the two failures reach it as `MailboxError` quoting the server's words. The row that asserts
this also asserts that the folder is listed, that the message is in it (`EXISTS 1`), that a search
of the folder is refused the same way, and that the connection survives the `NO`.

### Asking this server for the flag imap-tools never asks about

`folder.list()` sends the plain `LIST "" "*"`, so the newer attribute for "not a mailbox" cannot
reach the adapter through it. To see where that word comes from, drive imaplib directly against
the running probe, which is what
`test_the_newer_form_of_unselectable_is_a_word_this_server_really_sends` does, so
`just email-folder-probe` runs it for you:

```python
conn.xatom("LIST", "(SUBSCRIBED)", '""', '"*"')
conn.response("LIST")   # ('LIST', [b'(\\Subscribed \\NonExistent) "/" Ghost'])
conn.xatom("LIST", '""', '"*"', "RETURN (CHILDREN)")
conn.response("LIST")   # Parent is still (\Noselect \HasChildren) here
```

`\NonExistent` arrives instead of `\Noselect` and never beside it, on the subscribed name rather
than on the node, and `Ghost` is refused by a SELECT in the same words `Parent` is. The Bridge
cannot be asked at all: it advertises no LIST-EXTENDED and answers the extended form with `BAD`.

### And for the flag that lies, which is why the flag is asked rather than believed

`list_folders` drops a flagged name only when the server refuses it as a name no mailbox has,
because a `\Noselect` name really can open. `Feigned` is an ordinary mailbox that opens; its child
`Feigned/Followed` is subscribed and it is not, which is the state RFC 3501 has an `LSUB` of `%`
answer with `\Noselect` whatever the name really is. So the standard obliges a compliant server to
flag a mailbox that opens normally, and this one does:

```python
conn.lsub('""', '"%"')  # ('LSUB', [b'() "/" Ghost', b'(\\Noselect) "/" Feigned'])
conn.list()             # Feigned is (\HasChildren) here, and nothing else
conn.select('"Feigned"', readonly=True)   # ('OK', [b'0'])
```

The second line is the half that stays out of reach, and it is asserted too. In dovecot 2.3.21's
plain `LIST`, the listing the adapter itself makes, the flag and the refusal are computed from one
fact, so no name can be flagged there and still open; two configurations were tried against 2.3.21
to produce one and both failed, so the Bridge's own test stays the only live proof.

Re-run the probe after any change to the folder classification, and after a Dovecot bump if the
image reference ever moves: those wordings are the evidence the rule is built on. An edited image
reference announces itself, since `scripts/imagevolumes.py` is keyed on it and `just check` fails
on both the unrecorded new one and the orphaned old row until `just image-volumes` is re-run; a tag
republished under the same name does not.

