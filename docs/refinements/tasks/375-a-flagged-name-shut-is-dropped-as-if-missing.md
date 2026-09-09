# A flagged name that is merely shut is dropped as if no mailbox had it

**Status:** open, fix when it bites
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-09-09
**Trigger:** a server this repo can reach lists a name that is both flagged unselectable and refused
in words other than the ones that prove a folder missing. The reading is a plain `LIST "" "*"` taken
past the port, with every flagged name opened and its refusal kept: on the probe after
`just up-imap-probe`, and on the Bridge through `ImapMailbox`. This entry's trail records the flag
and the refusal each server answered with when that was last run.

Opened 2026-08-21 by the close of [374](374-two-names-the-bridge-lists-are-now-withheld.md), which
made `list_folders` open a flagged name and keep it only if the server opens it. `_opens` in
`brain/packages/email/src/cortex_email/imap.py` counts every `MailboxFolderSelectError` the same,
so a name that is flagged and refused is dropped whatever the refusal said. That is deliberate:
the promise the list makes is about names that work, and a name that will not open is not one.

It does leave an asymmetry nobody has seen a server produce. The probe's `Guarded` is a real
mailbox that an ACL has shut, it is not flagged, and it stays on the list because the port answers
the shut case with the base error rather than by hiding the name. A mailbox that was both flagged
and shut would be hidden instead, and the two cases differ only in a flag that says nothing about
being shut. Neither server this repo can reach produces one, and the probe cannot be made to, so
which behaviour is right is untested rather than decided.

**What would close it.** The obvious move was to give the probe's Dovecot a mailbox that is both
`\Noselect` and ACL-shut, since `docker/dovecot/probe-mailboxes.sh` already builds `Guarded` the one
way and `Parent` the other, and then to measure what it answers. That move was tried on 2026-09-08
and this server cannot make one. Its ACL backend is `acl = vfile` (`docker/dovecot/probe.conf`),
which reads a `dovecot-acl` file from inside the mailbox directory at
`<mailbox>/dbox-Mails/dovecot-acl`, and the absence of that `dbox-Mails` directory is exactly what
makes a name `\Noselect` here. Writing the ACL under `Parent` therefore shuts the name and unflags
it in the same edit; the trail records the before and after.

So closing this needs one of two things. Either a server on which the flag and the refusal are
separate facts, which dovecot 2.3.21 with sdbox and per-mailbox ACL files is not: the untried form
is dovecot's global `acl = vfile:<path>`, which names ACLs outside the mailbox directory, and it is
unmeasured whether a name with no mailbox directory can be shut that way or whether the existence
check that answers `Mailbox doesn't exist` still runs first. Or the question is settled by argument
instead of by measurement: keep dropping on any refusal, or drop only on the words that prove a
folder missing, which `_FOLDER_MISSING_ANSWERS` already spells and `_select` already reads. The
second matches the classification the rest of the adapter uses and costs nothing but a shared
helper. It was not simply done because the choice deserved a real answer from a real server, and the
finding above is that the servers here cannot give one.

## Trail

- 2026-08-21: Filed by the close of [374](374-two-names-the-bridge-lists-are-now-withheld.md),
  which narrowed the unselectable filter to names the server refuses as well as flags. Recorded in
  the ADR-0022 flagged-and-refused addendum.
- 2026-09-07: trigger swept, not fired, and narrowed. Neither reachable server produces the
  combination, and the probe cannot. Its only name flagged in a plain LIST is `Parent`, refused
  `NO Mailbox doesn't exist: Parent (0.001 + 0.000 secs).`, which is the words that prove a folder
  missing; its shut mailbox `Guarded` carries the ACL and no flag, and
  `docker/dovecot/probe-mailboxes.sh` writes the one `dovecot-acl` file under `Guarded` alone, so
  a name that is both flagged and shut does not exist there. The Bridge was read live today: 19
  names listed, `Folders` and `Labels` flagged `(\Noselect, \Unmarked)` and both opening, and
  all 19 of the listed names opening, so it refuses nothing at all. The old clause also named an
  observation nothing can make. A flagged name that is refused is dropped and does not open, so
  it can never appear among the names that open, and the live folder test's `offered == opens`
  can only come apart the other way, over a shut name the server never flagged. Recorded in the
  ADR-0022 trigger-sweep addendum.
- 2026-09-08: read again on both servers, still not fired, and the closing move above was tried and
  failed. The probe was started and `just email-folder-probe` passed all nine checks. Past the port,
  its plain LIST returns seven names and flags exactly one, `Parent (\Noselect \HasChildren)`,
  refused `NO Mailbox doesn't exist: Parent (0.001 + 0.000 secs).`, which is the words that prove a
  folder missing. `Guarded` is `(\HasNoChildren)` with no flag and is refused
  `NO [NOPERM] Permission denied (0.001 + 0.000 secs).`, so on this server the flag and the shut
  refusal sit on different names. The Bridge was read live the same day: 19 names listed, `Folders`
  and `Labels` flagged `('\Noselect', '\Unmarked')`, both opening, and not one listed name refused.
  Then the combination was built by hand. Creating `Parent/dbox-Mails` and writing `owner l` into
  `Parent/dbox-Mails/dovecot-acl` moved `Parent` from `(\Noselect \HasChildren)` refused
  `Mailbox doesn't exist: Parent` to `(\HasChildren)` refused `[NOPERM] Permission denied`: the file
  that shuts a name is the same file that stops this server calling the name unselectable. The
  store is a tmpfs, so `just down-imap-probe` put the fixture back. Recorded in the ADR-0022
  addendum of the same day.
- 2026-09-09: claims held against the code and the trigger read again on both servers, neither
  fired. `_opens` in `brain/packages/email/src/cortex_email/imap.py` still returns False for every
  `MailboxFolderSelectError` alike, `_select` still reads `_FOLDER_MISSING_ANSWERS`, and
  `docker/dovecot/probe-mailboxes.sh` still writes its one `dovecot-acl` under `Guarded`, which the
  plain LIST does not flag. The Bridge was read live today: 19 names listed, `Folders` and `Labels`
  flagged `('\Noselect', '\Unmarked')` and opening, and all 19 opening, so it refuses nothing and
  the combination has no producer here.
