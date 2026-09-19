# The dropped read under Dovecot's default is measured by hand and driven by no live test

**Status:** declined 2026-09-15
**Area:** email
**Origin:** [ADR-0057](../../adr/ADR-0057-imap-probe-server.md)

The probe's `docker/dovecot/probe.conf` sets `imap_fetch_failure = no-after`, so the read the server
declines reaches `ImapMailbox` as a `NO` and the live test in
`brain/packages/email/tests/test_imap_probe_live.py` drives the contract's declined-read case over
that. The default, `disconnect-immediately`, answers the same fault with
`* BYE FETCH failed: Internal error occurred. Refer to server log for more information.` and a
dropped connection, which the unit suite scripts as `DROPPED_READ` in
`brain/packages/email/tests/imap_stub.py` from a hand measurement made twice. One server runs one
setting, so the fixture cannot produce both on demand.

The adapter reads nothing of the abort on this path. `_search_failure` reads the exception type on
the search path, but a read by uid never reaches it: `_translated` wraps every library failure
alike, so a declined read is the same `MailboxError` containing the server's text under either
setting, and never `None`. A rewording on Dovecot's side would change what an operator reads in a
traceback and nothing the classification sees.

## History

- 2026-09-05: opened by the close of
  [551](551-a-read-the-server-refuses-is-measured-by-hand-and-driven-by-no-live-row.md), which
  measured both answers by hand and gave the fixture the `NO`.
- 2026-09-13: claims checked against the code and the trigger has not fired. The reason first given
  for leaving it was too narrow: the unit fixture's box exits without a logout and a real one logs
  out over the dropped connection, so under the default the message `_translated` wraps may be the
  logout's rather than the FETCH's.
- 2026-09-15: declined, on a measurement rather than on the argument. The probe was restarted with
  `imap_fetch_failure` at its default and the declined read taken through every layer: imaplib
  raises
  `IMAP4.abort('command: UID => FETCH failed: Internal error occurred. Refer to server log for more information. [2026-09-15 01:45:44]')`,
  which is `DROPPED_READ` word for word apart from the timestamp, so the hand measurement is
  confirmed by a second independent reading. The worry above is refuted at the same time: imaplib's
  `logout` expects the `BYE` and returns without raising, so the message `_translated` wraps is the
  FETCH's on the read path and the search path alike. What a second dovecot service would buy is a
  test asserting a string no classification reads, which does not justify a second service, a second
  published port and a second address for `just email-folder-probe` to find. The half of this that
  is a classification rather than words is filed as
  [673](673-the-search-paths-dropped-connection-is-driven-by-no-live-row.md).
