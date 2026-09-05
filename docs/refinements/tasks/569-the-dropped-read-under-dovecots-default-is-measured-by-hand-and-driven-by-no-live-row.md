# The dropped read under Dovecot's default is measured by hand and driven by no live row

**Status:** open, fix when it bites
**Area:** email
**Trigger:** a Dovecot left at its default `imap_fetch_failure` is found to answer a FETCH of a
message it cannot open with words other than `DROPPED_READ`'s, or the adapter starts reading an
abort's words rather than only its type.
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

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

**Why it was left.** The adapter reads nothing of the abort's words: imaplib's `IMAP4.abort`
becomes `MailboxError` by type, and the unit test asserts only that the text is carried. A
rewording on Dovecot's side would change what an operator reads in a traceback and nothing a
model or the classification sees.

**What would close it.** A second probe service in `docker/docker-compose.imap-probe.yml` on the
same image with the setting left at its default, or a second user whose configuration differs,
and a row that reads the abort off it; or a decision that a sentence the adapter never reads
needs no live row, recorded here.

## Trail

- 2026-09-05: opened by the close of
  [551](551-a-read-the-server-refuses-is-measured-by-hand-and-driven-by-no-live-row.md), which
  measured both answers by hand and gave the fixture the `NO`.
