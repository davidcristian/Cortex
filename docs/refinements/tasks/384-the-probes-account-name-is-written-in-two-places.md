# The probe's account name is written in the suite and again inside the script's mail root

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`brain/packages/email/tests/test_imap_probe_live.py` logs in as `probe`, written inline in the
`EmailConfig` the suite builds. `docker/dovecot/probe-mailboxes.sh` builds its tree under
`ROOT=/srv/mail/probe/Mail`, and that path is not arbitrary: `docker/dovecot/probe.conf` gives the
static userdb `home=/srv/mail/%Lu`, so the `probe` segment there is the account name. Rename the
account in the suite alone and dovecot looks in an empty home, every mailbox goes missing at once,
and the run looks like a server that lost its mail. That takes out the control test too, and the
suite is `integration`-marked, so CI never runs it.

It was left out of the earlier registration because it has no declaration to read: `crosscheck.py`
needs a name some file declares, and the account is an argument inside a constructor call. Hoisting
it to a module constant is a change to the suite rather than to the registry.

## History

- 2026-08-22: opened by the close of [R-366](366-the-probe-fixture-and-its-test-are-untied.md),
  which registered the probe's four mailbox names and found this fifth shared value while checking
  that entry's claim that the mailbox names were all the fixture and its suite share.
- 2026-08-23: closed as one registry row, `the probe's account`, declared at the suite's
  `PROBE_LOGIN` and matched as `/srv/mail/{value}` in the script at 2 occurrences. Half of what
  this entry proposed was already done: the refused-name measurement had hoisted the login to a
  module constant the day after this was written, so only the registration was missing. The entry
  is also one place short, since the script writes the home under `ROOT` and again in the `chown`
  seven lines later. This count is the ninth in the registry and differs from the guarded
  mailbox's: a half-applied rename here fails visibly, `set -eu` stopping the script, but only at
  the next measurement, whereas the registry row checks it on every commit. The password is one
  value and not two occurrences, the same constant used as both halves of a login nothing verifies,
  and the server stores no password to compare it with. The mail root above the account is not
  registrable here: `/srv/mail` appears in the script, in `probe.conf` and in the compose tmpfs,
  and no file declares it, so it appears inside the account's template as fixed text and the gap
  is filed as [R-390](390-the-probes-mail-root-is-written-in-three-files.md). Measured live
  against dovecot 2.3.21 as well as against the text: the suite passes 6 of 6, renaming the
  account in the script alone fails all 6 including the control, and the revert passes 6 again.
  Five planted changes each exited 1 and were restored by digest, and the matching rename on both
  sides left the check passing.
