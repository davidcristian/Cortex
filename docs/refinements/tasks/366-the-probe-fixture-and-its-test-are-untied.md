# The IMAP probe's fixture names are spelled twice and nothing ties the two spellings

**Status:** landed 2026-08-22
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-21 by the close of [327](327-the-other-no-to-select-is-unseen.md), which added a
second IMAP server as a measurement fixture and left this residue. The probe's mailboxes are built
by `docker/dovecot/probe-mailboxes.sh` and named again by `test_imap_probe_live.py`: `Guarded`,
the mailbox whose ACL is what makes the whole measurement possible, plus the `\Noselect` parent
and the one folder that opens. Rename one in the script and the other side goes on naming a
mailbox that is no longer built. Neither the address nor the port is part of this, deliberately:
the recipe reads both back off docker, the publish when it answers and the container's own
address when it does not, so neither is written down anywhere a rename could strand.

That is exactly the drift `crosscheck.py` exists to catch, and its registry does not hold these. The
suite that would catch it is integration-marked, so it never runs in CI and the gates keep passing
while the fixture and its test disagree, which is the shape of failure the registry's own docstring
describes.

**What would close it.** The entry is a registry decision more than a code change. The values are a
Python test module's constants against a shell script's paths, which is neither the language
boundary `seamcouplings.py` names nor the brain container's shipped defaults `shippedcouplings.py`
holds, so the first question is whether they join an existing part, on a reading of its subject that
stretches to cover a fixture, or whether a new part names the subject accurately, which
`registry.py` is built to take (one data file plus one line). Then the entries themselves: sites in
the test module, mentions rendering each name into the path the script writes it in. The neighbours
worth reading first are [354](354-two-declared-defaults-the-reducer-refuses.md) and
[355](355-one-variable-several-defaults-no-declaration.md), which ask the same question about other
far sides the scan cannot currently reach.

## Trail

- 2026-08-21: Filed by the close of [327](327-the-other-no-to-select-is-unseen.md), which built the
  probe stack and its live suite and left their shared names unregistered rather than forcing a
  registry taxonomy decision inside a measurement slice.
- 2026-08-22: landed. **The taxonomy question is answered with a new part**,
  `scripts/fixturecouplings.py`, the seventh, added the way `emailcouplings.py` was two days
  earlier: a data file plus one line in `registry.py`, with the scan never learning the registry
  grew. Joining the email part would have made its own docstring false, its subject being the
  sidecar's shipped env answers and not a dovecot fixture's mailbox tree; the distinction that holds
  is that every other part ties something the repo ships and this one ties something it measures
  with, which generalises to the next fixture without stretching. **Two claims did not re-derive:**
  the two files share four names and not three (`INBOX` joins `Guarded`, `Parent` and
  `Parent/Child`, and all four are registered), and the mailbox names are not the whole of what they
  share, the account `probe` being spelled in the suite and again inside the script's mail root
  ([R-384](384-the-probe-account-is-spelled-twice.md)). The deliberate exclusions held: the address
  and the port stay out, the recipe reading both back off docker. The guarded mailbox's mention pins
  2 occurrences, the directory and the ACL file inside it being one set. Nine planted drifts, each
  exiting 1 and restored by digest, including the half applied rename the count exists for. Tabled
  in the ADR-0029 fixture addendum.
