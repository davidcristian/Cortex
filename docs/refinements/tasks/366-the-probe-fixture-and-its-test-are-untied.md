# The IMAP probe's fixture names are spelled twice and nothing ties the two spellings

**Status:** open, actionable
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

That is exactly the drift `crosscheck.py` exists to catch, and its registry does not hold these.
The suite that would notice is integration-marked, so it never runs in CI and the gates stay green
while the fixture and its test disagree, which is the shape of failure the registry's own docstring
describes.

**What would close it.** The entry is a registry decision more than a code change. The values are a
Python test module's constants against a shell script's paths, which is neither the language
boundary `seamcouplings.py` names nor the brain container's shipped defaults `shippedcouplings.py`
holds, so the first question is whether they join an existing part, on a reading of its subject
that stretches to cover a fixture, or whether a new part names the subject honestly, which
`registry.py` is built to take (one data file plus one line). Then the entries themselves: sites in
the test module, mentions rendering each name into the path the script writes it in. The neighbours
worth reading first are [354](354-two-declared-defaults-the-reducer-refuses.md) and
[355](355-one-variable-several-defaults-no-declaration.md), which ask the same question about other
far sides the scan cannot currently reach.

## Trail

- 2026-08-21: Filed by the close of [327](327-the-other-no-to-select-is-unseen.md), which built the
  probe stack and its live suite and left their shared names unregistered rather than forcing a
  registry taxonomy decision inside a measurement slice.
