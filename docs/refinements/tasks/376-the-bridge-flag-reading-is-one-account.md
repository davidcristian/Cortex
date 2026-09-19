# The kept half of the folder filter is proved only on a server nobody here can configure

**Status:** done 2026-08-23
**Area:** email-confirmer
**Origin:** [ADR-0057](../../adr/ADR-0057-imap-probe-server.md)

`list_folders` keeps a flagged name that opens. The dropped half is covered by a server this repo
builds: the probe's Dovecot lists `Parent`, refuses it, and `test_imap_probe_live.py` says so. The
kept half had no such server. The only place a `\Noselect` name that opens exists is the live
ProtonMail Bridge, on one account, whose folder tree is whatever that account happens to hold.

So the evidence for half the rule was a measurement of somebody's mailbox rather than a fixture,
and it goes stale the way any account does. The stand-in has the Bridge's flags word for word as
`OPEN_NODE_FLAGS`, which keeps the unit tests accurate about the shape, but a stand-in cannot show
that a real server still behaves that way.

Closing it means adding a mailbox to `docker/docker-compose.imap-probe.yml` that Dovecot lists with
an unselectable flag and still opens, if that server can be made to produce one, and asserting the
keep in `test_imap_probe_live.py` beside the drop it already asserts. If Dovecot cannot, that is
itself the finding.

## History

- 2026-08-21: Filed by the close of [374](374-two-names-the-bridge-lists-are-now-withheld.md),
  whose live measurement of the Bridge was the only evidence that a flagged name which opens is
  kept. Recorded in ADR-0056 decision 8.
- 2026-08-23: Done as the `Feigned` pair in `docker/dovecot/probe-mailboxes.sh`, asserted live in
  `brain/packages/email/tests/test_imap_probe_live.py` and registered in
  `scripts/fixturecouplings.py`. The premise is now measured on a server this repo builds: RFC 3501
  obliges an `LSUB` of `%` to flag an unsubscribed name with subscribed children `\Noselect`, so
  Dovecot 2.3.21 flags `Feigned` there and opens it. The listing the adapter itself makes is a
  different answer: two configurations were built to move the flag into a plain `LIST` and both
  failed, so the keep in that listing stays proved only against the Bridge. That half went to
  [400](400-the-keep-in-the-adapters-listing-is-one-account.md) and the untried configurations to
  [401](401-the-rejected-probe-configurations-are-prose.md). The measurements are in
  [docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md).
