# Two dovecot configurations were measured and rejected, and nothing runs them again

**Status:** declined 2026-09-12
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-23 by the close of
[376](376-the-bridge-flag-reading-is-one-account.md), which built two probe configurations to see
whether dovecot could be made to flag a name in a plain LIST and still open it, measured both,
and rejected both.

The measurements are in the ADR-0022 flagged-name-that-opens addendum as a table: a second
namespace whose prefix collides with a real mailbox lists that name twice and refuses the flagged
reading, and a namespace prefixed `INBOX/` is merged with the real INBOX and carries no flag at
all. Neither exists as anything runnable. The probe stack ships one configuration,
`docker/dovecot/probe.conf`, and the two rejected ones were written into a scratch directory and
thrown away with it.

That is the right shape for a negative result nobody needs to reproduce, and the wrong shape for
one the pinned image could overturn without anyone noticing. The image is pinned precisely because the wordings it
produces are the evidence the folder classification is built on, and the runbook already says to
rerun the probe after a bump. A bump that made either configuration work would make the flag rule
provable in the listing that matters ([400](400-the-keep-in-the-adapters-listing-is-one-account.md))
and nothing would say so.

**What would close it.** Decide which of the two is worth keeping, and keep only that one: the
namespace collision, which is the near miss, and which needs a second `.conf` and a compose profile
or override rather than a second stack. Then a rerun after a bump is one command instead of a
reading of prose and an afternoon of rebuilding what somebody already built. The honest alternative
is to decline it and let the addendum's table be the record, on the grounds that a fixture no test
asserts over will not be run; the reason to prefer keeping it is that the table's own
value is entirely in being reproducible.

## Trail

- 2026-08-23: opened by the close of
  [376](376-the-bridge-flag-reading-is-one-account.md), whose finding rests on two configurations
  that were built, measured, and left as a table in prose.
- 2026-09-07: trigger swept, not fired, and narrowed. The image line has not changed since the
  commit that added the probe stack, which is the only commit `git log -S` over that file returns
  for it, and the tag still resolves to the image this host measured against:
  `docker manifest inspect` and `docker image inspect` agree on the digest the ADR-0022
  trigger-sweep addendum records. The old clause read the text of the pin alone, which a re-push
  of the same tag leaves untouched, and a re-push is the way this particular pin can move without
  anyone editing anything, so the clause now names the digest as well.
- 2026-09-09: claims held against the code and the trigger read again on both limbs, neither
  fired. `docker/docker-compose.imap-probe.yml` still names `dovecot/dovecot:2.3.21`, and that tag
  still resolves to the recorded
  `sha256:1c18c756f20d03867077a1b509a6e2e3008ab1eafa56377b6f2eca12dc1ba581`, in the registry
  (`docker manifest inspect --verbose`) and in the copy cached on this host
  (`docker image inspect`). The probe stack still ships one configuration: `docker/dovecot/` holds
  `probe.conf` and `probe-mailboxes.sh` and nothing else, and the table of the two rejected
  configurations is still prose in the ADR-0022 flagged-name-that-opens addendum.
- **2026-09-12, declined** on the alternative this entry named, with two readings that were not
  available when it was written. Neither trigger limb had fired:
  `docker/docker-compose.imap-probe.yml` still names `dovecot/dovecot:2.3.21`, and that tag still
  resolves to `sha256:1c18c756f20d03867077a1b509a6e2e3008ab1eafa56377b6f2eca12dc1ba581` in the
  registry and in this host's cache.
  **The harm was half covered already.** This entry rested on a bump landing with nothing saying so,
  and an edited pin cannot: `scripts/imagevolumes.py` is keyed on the image reference a compose file
  writes, so `check-volumecheck` fails on both the unrecorded new reference and the orphaned old
  row. Measured by editing the tag to `dovecot/dovecot:2.4.1` and running the gate, which reported
  exactly those two faults and went green again on restore. What stays invisible is a tag
  republished under the same name, which is the exposure
  [433](433-a-mutable-image-tag-moves-under-the-recorded-answer.md) weighed and declined.
  **The keeping move costs more than the entry said.** It is not a second `.conf` and a compose
  override: `docker/dovecot/probe-mailboxes.sh` builds the tree the live suite pins by name and
  `scripts/fixturecouplings.py` holds its mailbox names to that suite's constants, so a
  configuration that needs a colliding `Shared` mailbox needs a second tree-builder and a registry
  decision for the name, on top of an override joining three compose gates. That is a real fixture
  bought to make a negative result rerunnable, and nothing would assert over it. The value the entry
  was protecting is in the runbook instead: the rerun-after-a-bump paragraph now says to rebuild the
  two configurations by hand and why a different resolution of the namespace collision would matter,
  and names what an edited pin does and does not announce. Recorded in the ADR-0022 addendum on what
  the list drops.
