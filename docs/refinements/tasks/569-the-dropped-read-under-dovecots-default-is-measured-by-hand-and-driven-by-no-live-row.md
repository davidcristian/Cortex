# The dropped read under Dovecot's default is measured by hand and driven by no live row

**Status:** open, fix when it bites
**Area:** email
**Trigger:** a Dovecot left at its default `imap_fetch_failure` is found to answer a FETCH of a
message it cannot open with words other than `DROPPED_READ`'s, or the adapter starts reading an
abort's words rather than only its type.
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-09-13

Opened 2026-09-05 by the close of
[551](551-a-read-the-server-refuses-is-measured-by-hand-and-driven-by-no-live-row.md), which
found that Dovecot's answer to a FETCH it cannot complete is chosen by `imap_fetch_failure` and
set the probe to the one value that answers a tagged `NO`.

The probe's `docker/dovecot/probe.conf` sets `imap_fetch_failure = no-after`, so the read it
declines reaches `ImapMailbox` as a `NO` and the live row in
`brain/packages/email/tests/test_imap_probe_live.py` drives the contract's declined-read check
over that. The default, `disconnect-immediately`, answers the same fault with `* BYE FETCH
failed: Internal error occurred. Refer to server log for more information.` and a dropped
connection, which the unit suite scripts as `DROPPED_READ` in
`brain/packages/email/tests/imap_stub.py` from a hand measurement made twice, on 2026-09-05
before the setting was found and again while it was being measured. One server runs one setting,
so the fixture cannot produce both on demand.

**Why it was left.** The adapter reads nothing of the abort at all on this path. `_search_failure`
reads the type on the search path, but a read by uid never reaches it: `_translated` wraps every
library failure alike, so a declined read is the same `MailboxError` carrying the server's text
under either setting, and never `None`. A rewording on Dovecot's side would change what an
operator reads in a traceback and nothing a model or the classification sees.

The words are further from proven than the fixture makes them look. `FakeBox.__exit__` in
`imap_stub.py` returns without sending anything, while imap-tools' `MailBox.__exit__` calls
`logout()`, which under the default is sent over a connection the server has already dropped and
raises in its own right. That second failure is raised while the first is being handled and is the
one `_translated` wraps, so the traceback an operator reads under the default may carry the
logout's words rather than the FETCH's. Nothing in the unit suite can show which, and the answer
changes no classification.

**What would close it.** A second probe service in `docker/docker-compose.imap-probe.yml` on the
same image with the setting left at its default, or a second user whose configuration differs,
and a row that reads the abort off it, which would also settle which failure's words survive the
cleanup; or a decision that words no classification reads need no live row, recorded here.

## Trail

- 2026-09-05: opened by the close of
  [551](551-a-read-the-server-refuses-is-measured-by-hand-and-driven-by-no-live-row.md), which
  measured both answers by hand and gave the fixture the `NO`.
- 2026-09-13: claims held against the code, the trigger has not fired, and the reason the entry
  gives for leaving it was too narrow. The probe still sets `imap_fetch_failure = no-after`, the
  live row still drives the declined-read check over the `NO`, and `DROPPED_READ` is unchanged, so
  neither half of the trigger has happened. What the re-derivation added is the cleanup: the unit
  fixture's box exits without a logout and a real one logs out over the dropped connection, so
  under the default the message `_translated` wraps is probably the logout's rather than the
  FETCH's. The fail-safe outcome is unchanged either way, a `MailboxError` and never `None`, which
  is why this stays open rather than becoming urgent.
