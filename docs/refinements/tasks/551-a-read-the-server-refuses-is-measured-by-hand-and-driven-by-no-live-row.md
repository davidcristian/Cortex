# A read the server refuses is measured by hand and driven by no live row

**Status:** landed 2026-09-05
**Area:** email
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-09-05 by the close of
[548](548-an-empty-folder-read-raises-instead-of-answering-not-found.md), which reads a message's
absence off a `UID FETCH`'s `OK` with no data and keeps every other answer a `MailboxError`, and
could produce the other answer only by hand.

A read the server declines for a reason of its own is the case the fail-safe direction exists
for: it must never be reported as a message that is not there. No server this repo can reach
answers a `UID FETCH` with `NO`. Against Proton Mail Bridge 03.26.00 and Dovecot 2.3.21 a uid no
message has answers `OK` with no data in a folder holding mail and in one holding none, a string
that is not a number answers `BAD`, and on Dovecot a message another session had expunged still
answers the whole-message FETCH `OK` with no data. The one declined read that could be produced
took a hand-run step the probe fixture does not perform: a message appended to `Feigned` and its
dbox file made unreadable to the mail process (`chown root` and `chmod 000` inside the container),
after which Dovecot answers `* BYE FETCH failed: Internal error occurred. Refer to server log for
more information.` and drops the connection. So the contract's declined-read check is driven by
two scripted answers in `brain/packages/email/tests/imap_stub.py`: `DROPPED_READ`, that measured
sentence, and `DECLINED_READ_ANSWER`, a `NO [UNAVAILABLE]` this repo wrote, which no live row
drives and which the fixture cannot produce on demand.

**What would close it.** A mailbox in `docker/dovecot/probe-mailboxes.sh` built with one message
whose file the mail process cannot open, so the probe suite gains a row driving
`a_read_the_server_declined_is_not_reported_as_not_there` over the live refusal, the shape
`test_a_mailbox_that_exists_and_will_not_open_is_never_reported_missing` already has. The dbox
format needs its index to know the message, so the append has to happen through IMAP after the
server starts and the permission change after that, which the entrypoint cannot do on its own;
a recipe step, or a probe row that does both itself before it fetches, would. Whatever the fixture
then produces on demand replaces the written `NO` if it is one, or retires it if a real declined
read on this server is only ever the BYE.

## Trail

- 2026-09-05: opened by the close of
  [548](548-an-empty-folder-read-raises-instead-of-answering-not-found.md), which measured the
  BYE by hand and left the written `NO` labelled as written.
- 2026-09-05: landed. Re-derived on the probe's Dovecot 2.3.21, which answer a failed FETCH gets
  is the server's `imap_fetch_failure` setting: the default `disconnect-immediately` is the BYE
  measured by hand, `disconnect-after` is the same BYE for a one-message FETCH, and `no-after`
  answers `NO [SERVERBUG] Internal error occurred. Refer to server log for more information.`
  on a connection that stays open. So the entry's second outcome, that a declined read on this
  server is only ever the BYE, was a configuration rather than a fact, and the entry was right
  that the entrypoint cannot append the message on its own (`doveadm save` fails with
  `connect(/run/dovecot/auth-userdb) failed` before the server has started, which `probe.conf`
  had claimed the opposite of). The other candidates were measured and none produces a `NO`: a
  removed file rebuilds the index and drops the session, and an ACL written mid-session is read
  only by the next SELECT. `docker/dovecot/probe.conf` now sets `no-after`,
  `docker/dovecot/probe-mailboxes.sh` builds `Sealed`, a mailbox holding one message saved
  through a first loopback-only start of the server and shut before the second, the contract's
  `MailboxUnderTest` names the uid a declined read is of (`declined_uid`), the probe suite drives
  `a_read_the_server_declined_is_not_reported_as_not_there` over the live refusal, and the
  stand-in's `DECLINED_READ_ANSWER` is the measured sentence. Written up in the
  [ADR-0022 addendum on the read a server declines](../../adr/ADR-0022-email-write-confirmer.md#addendum-2026-09-05-the-read-a-server-declines-produced-by-the-probe-and-measured-as-a-no),
  with the mutation table. Opens
  [569](569-the-dropped-read-under-dovecots-default-is-measured-by-hand-and-driven-by-no-live-row.md)
  and
  [570](570-a-search-of-a-folder-holding-one-unreadable-message-is-refused-whole.md).
