# The kept half of the folder filter is proved only on a server nobody here can configure

**Status:** landed 2026-08-23
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-21 by the close of [374](374-two-names-the-bridge-lists-are-now-withheld.md), which
made `list_folders` keep a flagged name that opens. The dropped half is pinned on a server this
repo builds: the probe's Dovecot lists `Parent`, refuses it, and
`test_imap_probe_live.py` says so. The kept half has no such server. The only place a
`\Noselect` name that opens exists is the live ProtonMail Bridge, on one account, whose folder
tree is whatever that account happens to hold; the probe has no such name and cannot grow one
without being told to.

So the evidence for half the rule is a measurement of somebody's mailbox rather than a fixture,
and it goes stale the way any account does. The stand-in carries the Bridge's flags verbatim as
`OPEN_NODE_FLAGS`, which keeps the unit tests honest about the shape, but a stand-in cannot show
that a real server still behaves that way.

**What would close it.** Add a mailbox to `docker/docker-compose.imap-probe.yml` that Dovecot
lists with an unselectable flag and still opens, if that server can be made to produce one at all,
and assert the keep in `test_imap_probe_live.py` beside the drop it already asserts. If Dovecot
cannot be made to list an openable `\Noselect` name, that is itself the finding and this closes as
declined with it written down, leaving the Bridge test as the only live proof and saying why.

## Trail

- 2026-08-21: Filed by the close of [374](374-two-names-the-bridge-lists-are-now-withheld.md),
  whose live measurement of the Bridge is currently the only evidence that a flagged name which
  opens is kept. Recorded in the ADR-0022 flagged-and-refused addendum.
- 2026-08-23: Landed as the `Feigned` pair in `docker/dovecot/probe-mailboxes.sh`, asserted live in
  `brain/packages/email/tests/test_imap_probe_live.py` and tied in `scripts/fixturecouplings.py`.
  The premise is now measured on a server this repo builds: RFC 3501 obliges an `LSUB` of `%` to
  flag an unsubscribed name with subscribed children `\Noselect`, so Dovecot 2.3.21 flags `Feigned`
  there and opens it. The listing the adapter itself makes is a different answer, and it is the one
  this file asked for: two configurations were built to move the flag into a plain `LIST` and both
  failed, so the keep in that listing stays proved only against the Bridge. That half went to
  [400](400-the-keep-in-the-adapters-listing-is-one-account.md) and the unrun configurations to
  [401](401-the-rejected-probe-configurations-are-prose.md). The measurements, both directions, are
  in the ADR-0022 flagged-name-that-opens addendum.
