# Two dovecot configurations were measured and rejected, and nothing runs them again

**Status:** declined 2026-09-12
**Area:** email-confirmer
**Origin:** [ADR-0057](../../adr/ADR-0057-imap-probe-server.md)

The measurements are in
[docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md): a second namespace
whose prefix collides with a real mailbox lists that name twice and refuses the flagged reading,
and a namespace prefixed `INBOX/` is merged with the real INBOX and has no flag at all. Neither
exists as anything runnable. The probe stack ships one configuration,
`docker/dovecot/probe.conf`, and the two rejected ones were written into a scratch directory and
thrown away with it.

That is the right shape for a negative result nobody needs to reproduce, and the wrong shape for
one a new image version could overturn without anyone noticing. The image version is fixed
precisely because the wordings it produces are the evidence the folder classification is built on,
and the runbook already says to rerun the probe after a version change. A version change that made
either configuration work would make the flag rule provable in the listing that matters
([400](400-the-keep-in-the-adapters-listing-is-one-account.md)) and nothing would say so.

## History

- 2026-08-23: opened by the close of
  [376](376-the-bridge-flag-reading-is-one-account.md), whose finding rests on two configurations
  that were built, measured, and left as a table in prose.
- 2026-09-07: trigger checked, not fired, and narrowed. The image line has not changed since the
  commit that added the probe stack, the only commit `git log -S` over that file returns for it,
  and the tag still resolves to the image this host measured against: `docker manifest inspect` and
  `docker image inspect` agree on the digest recorded in
  [docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md). The old clause
  read the text of the version alone, which a re-push of the same tag leaves untouched, and a
  re-push is how this version can move without anyone editing anything, so the clause now names the
  digest as well.
- 2026-09-09: claims checked against the code and the trigger read again on both parts, neither
  fired. `docker/docker-compose.imap-probe.yml` still names `dovecot/dovecot:2.3.21`, and that tag
  still resolves to the recorded
  `sha256:1c18c756f20d03867077a1b509a6e2e3008ab1eafa56377b6f2eca12dc1ba581`, in the registry
  (`docker manifest inspect --verbose`) and in the copy cached on this host
  (`docker image inspect`). The probe stack still ships one configuration: `docker/dovecot/`
  contains `probe.conf` and `probe-mailboxes.sh` and nothing else.
- 2026-09-12: declined, with two readings that were not available when this was written. Neither
  trigger part had fired: the compose file still names `dovecot/dovecot:2.3.21`, resolving to the
  recorded digest in the registry and in this host's cache. The harm was half covered already. This
  entry rested on a version change arriving with nothing saying so, and an edited version cannot:
  `scripts/imagevolumes.py` is keyed on the image reference a compose file writes, so
  `check-volumecheck` fails on both the unrecorded new reference and the orphaned old row. Measured
  by editing the tag to `dovecot/dovecot:2.4.1` and running the check, which reported exactly those
  two faults and passed again on restore. What stays invisible is a tag republished under the same
  name, the exposure [433](433-a-mutable-image-tag-moves-under-the-recorded-answer.md) weighed and
  declined. Keeping a configuration costs more than this entry said. It is not a second `.conf` and
  a compose override: `docker/dovecot/probe-mailboxes.sh` builds the tree the live suite checks by
  name and `scripts/fixturecouplings.py` ties its mailbox names to that suite's constants, so a
  configuration that needs a colliding `Shared` mailbox needs a second tree-builder and a registry
  decision for the name, on top of an override joining three compose checks. That is a real fixture
  bought to make a negative result rerunnable, and nothing would assert over it. The value this
  entry was protecting is in the runbook instead: the paragraph about rerunning after a version
  change now says to rebuild the two configurations by hand, why a different resolution of the
  namespace collision would matter, and what an edited version does and does not report.
