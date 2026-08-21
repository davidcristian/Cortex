# A flagged name that is merely shut is dropped as if no mailbox had it

**Status:** open, fix when it bites
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Trigger:** A server this repo talks to refusing a `\Noselect` name for a reason that is not its
name, which the live folder test surfaces as a name that opened and was not offered.

Opened 2026-08-21 by the close of [374](374-two-names-the-bridge-lists-are-now-withheld.md), which
made `list_folders` open a flagged name and keep it only if the server opens it. `_opens` in
`brain/packages/email/src/cortex_email/imap.py` counts every `MailboxFolderSelectError` the same,
so a name that is flagged and refused is dropped whatever the refusal said. That is deliberate:
the promise the list makes is about names that work, and a name that will not open is not one.

It does leave an asymmetry nobody has seen a server produce. The probe's `Guarded` is a real
mailbox that an ACL has shut, it is not flagged, and it stays on the list because the port answers
the shut case with the base error rather than by hiding the name. A mailbox that was both flagged
and shut would be hidden instead, and the two cases differ only in a flag that says nothing about
being shut. Neither server this repo can reach produces one, so which behaviour is right is
untested rather than decided.

**What would close it.** Give the probe's Dovecot a mailbox that is both `\Noselect` and ACL-shut
(`docker/docker-compose.imap-probe.yml` already builds `Guarded` that way and `Parent` the other),
measure what it answers, and then choose: keep dropping on any refusal, or drop only on the words
that prove a folder missing, which `_FOLDER_MISSING_ANSWERS` already spells and `_select` already
reads. The second is the one that matches the classification the rest of the adapter uses, and it
costs nothing but a shared helper. The reason it was not simply done is that the choice deserves a
real answer from a real server rather than a symmetry argument.

## Trail

- 2026-08-21: Filed by the close of [374](374-two-names-the-bridge-lists-are-now-withheld.md),
  which narrowed the unselectable filter to names the server refuses as well as flags. Recorded in
  the ADR-0022 flagged-and-refused addendum.
