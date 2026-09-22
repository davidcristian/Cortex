# The IMAP probe's fixture names are written twice and nothing compares them

**Status:** done 2026-08-22
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

The probe's mailboxes are built by `docker/dovecot/probe-mailboxes.sh` and named again by
`test_imap_probe_live.py`: `Guarded`, the mailbox whose ACL makes the whole measurement possible,
plus the `\Noselect` parent and the one folder that opens. Rename one in the script and the other
side goes on naming a mailbox that is no longer built. Neither the address nor the port is part of
this, deliberately: the recipe reads both back off docker, so neither is written down anywhere a
rename could break.

That is the divergence `crosscheck.py` exists to catch, and its registry did not hold these. The
suite that would catch it is `integration` marked, so it never runs in CI and the checks keep
passing while the fixture and its test disagree.

It is a registry decision more than a code change. The values are a Python test module's constants
against a shell script's paths, which is neither the language boundary `wirecouplings.py` names nor
the brain container's shipped defaults `shippedcouplings.py` holds, so the first question is
whether they join an existing part or whether a new part names the subject accurately, which
`registry.py` is built to take (one data file plus one line). Then the entries: declarations in the
test module, mentions rendering each name into the path the script writes it in.

## History

- 2026-08-21: Filed by the close of [327](327-the-other-no-to-select-is-unseen.md), which built the
  probe stack and its live suite and left their shared names unregistered rather than forcing a
  registry taxonomy decision inside a measurement slice.
- 2026-08-22: Done. The taxonomy question is answered with a new part,
  `scripts/fixturecouplings.py`, the seventh, added the way `emailcouplings.py` was two days
  earlier: a data file plus one line in `registry.py`, with the scan never learning the registry
  grew. Joining the email part would have made its own docstring false, its subject being the
  sidecar's shipped environment answers and not a dovecot fixture's mailbox tree; the distinction
  that holds is that every other part compares something the repo ships and this one compares
  something it measures with. Two claims did not hold: the two files share four names and not three
  (`INBOX` joins `Guarded`, `Parent` and `Parent/Child`, and all four are registered), and the
  mailbox names are not the whole of what they share, the account `probe` being written in the
  suite and again inside the script's mail root
  ([R-384](384-the-probes-account-name-is-written-in-two-places.md)). The deliberate exclusions held: the address
  and the port stay out. The guarded mailbox's mention fixes 2 occurrences, the directory and the
  ACL file inside it being one set. Nine planted differences, each exiting 1 and restored by
  digest, including the half applied rename the count exists for. Recorded in ADR-0042.
