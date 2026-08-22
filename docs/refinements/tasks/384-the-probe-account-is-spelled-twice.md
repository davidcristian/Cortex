# The probe's account name is spelled in the suite and again inside the script's mail root

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-22 by the close of [R-366](366-the-probe-fixture-and-its-test-are-untied.md), which
registered the probe's four mailbox names and found one more value the two files share.

`brain/packages/email/tests/test_imap_probe_live.py` logs in as `probe`, spelled inline in the
`EmailConfig` the suite builds. `docker/dovecot/probe-mailboxes.sh` builds its tree under
`ROOT=/srv/mail/probe/Mail`, and that path is not arbitrary: `docker/dovecot/probe.conf` gives the
static userdb `home=/srv/mail/%Lu`, so the segment spelled `probe` there **is** the account name.
Rename the account in the suite alone and dovecot looks in an empty home, every mailbox goes
missing at once, and the run reads as a server that lost its mail rather than as a fixture built
for somebody else.

That is a worse failure than any of the four the mailbox names produce, since it takes out the
control test too, and the same thing makes it invisible: the suite is `integration`-marked and
never runs in CI.

**Why it was left.** It has no declaration to read. `crosscheck.py` needs at least one site, a name
a file declares, and the account is an argument inside a constructor call rather than a module
constant. Hoisting it is a change to the suite rather than to the registry, which is a different
kind of edit from the four rows that closed, and doing it inside that close would have hidden a
code change under a taxonomy decision.

**What would close it.** Hoist the account to a module constant beside the four mailbox names, the
same remedy the compose survey has paid eleven times, and register it in
`scripts/fixturecouplings.py` with a mention rendering it into the script's `ROOT`. Read the
password while there: it is the same word and is checked by nothing (`nopassword=y`), so whether it
is one value or two spellings of one is worth a sentence either way. The mail root's own `/srv/mail`
prefix is shared with `probe.conf` and with the compose tmpfs, which is a second coupling in the
same three files and probably one row rather than three.

## Trail

- 2026-08-22: opened by the close of [R-366](366-the-probe-fixture-and-its-test-are-untied.md),
  which found this while re-deriving that entry's claim that the mailbox names were the whole of
  what the fixture and its suite share.
