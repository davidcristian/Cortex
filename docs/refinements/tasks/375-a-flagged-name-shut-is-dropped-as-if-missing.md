# A flagged name that is merely closed is dropped as if no mailbox had it

**Status:** done 2026-09-12
**Area:** email-confirmer
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

`_opens` in `brain/packages/email/src/cortex_email/imap.py` treated every
`MailboxFolderSelectError` the same, so a name that is flagged and refused was dropped whatever the
refusal said. That was deliberate: the promise the list makes is about names that work.

It leaves an asymmetry nobody has seen a server produce. The probe's `Guarded` is a real mailbox
that an ACL has closed, it is not flagged, and it stays on the list because the port answers the
closed case with the base error rather than by hiding the name. A mailbox that was both flagged and
closed would be hidden instead, and the two cases differ only in a flag that says nothing about
being closed.

The obvious way to decide it was to give the probe's Dovecot a mailbox that is both `\Noselect` and
ACL-closed and measure what it answers. That was tried on 2026-09-08 and this server cannot make
one. Its ACL backend is `acl = vfile` (`docker/dovecot/probe.conf`), which reads a `dovecot-acl`
file from inside the mailbox directory at `<mailbox>/dbox-Mails/dovecot-acl`, and the absence of
that `dbox-Mails` directory is exactly what makes a name `\Noselect` here. Writing the ACL under
`Parent` closes the name and unflags it in the same edit.

So closing it needs either a server on which the flag and the refusal are separate facts, which
dovecot 2.3.21 with sdbox and per-mailbox ACL files is not, or a decision by argument: keep
dropping on any refusal, or drop only on the words that prove a folder missing, which
`_FOLDER_MISSING_ANSWERS` already holds and `_select` already reads.

## History

- 2026-08-21: Filed by the close of [374](374-two-names-the-bridge-lists-are-now-withheld.md),
  which narrowed the unselectable filter to names the server refuses as well as flags. Recorded in
  ADR-0056 decision 8.
- 2026-09-07: Trigger checked, not fired, and narrowed. Neither reachable server produces the
  combination. The probe's only name flagged in a plain LIST is `Parent`, refused `NO Mailbox
  doesn't exist: Parent (0.001 + 0.000 secs).`; its closed mailbox `Guarded` has the ACL and no
  flag. The Bridge was read live: 19 names listed, `Folders` and `Labels` flagged `(\Noselect,
  \Unmarked)` and both opening, and all 19 opening, so it refuses nothing. The old trigger also
  named an observation nothing can make: a flagged name that is refused is dropped and does not
  open, so it can never appear among the names that open.
- 2026-09-08: Read again on both servers, still not fired, and the closing move was tried and
  failed. Past the port, the probe's plain LIST returns seven names and flags exactly one, `Parent
  (\Noselect \HasChildren)`, refused `NO Mailbox doesn't exist: Parent (0.001 + 0.000 secs).`.
  `Guarded` is `(\HasNoChildren)` with no flag and is refused `NO [NOPERM] Permission denied (0.001
  + 0.000 secs).`. The Bridge was read the same day: 19 names, `Folders` and `Labels` flagged, both
  opening, none refused. Then the combination was built by hand: creating `Parent/dbox-Mails` and
  writing `owner l` into `Parent/dbox-Mails/dovecot-acl` moved `Parent` from `(\Noselect
  \HasChildren)` refused `Mailbox doesn't exist: Parent` to `(\HasChildren)` refused `[NOPERM]
  Permission denied`. The store is a tmpfs, so `just down-imap-probe` put the fixture back.
- 2026-09-09: Claims checked against the code and the trigger read again on both servers, neither
  fired. `_opens` still returns False for every `MailboxFolderSelectError` alike, `_select` still
  reads `_FOLDER_MISSING_ANSWERS`, and `docker/dovecot/probe-mailboxes.sh` still writes its one
  `dovecot-acl` under `Guarded`, which the plain LIST does not flag.
- 2026-09-12: Fixed by the second option, settling the question by argument once three reviews had
  established that no server here can answer it. The argument was not a preference:
  `mailbox_contract.py` already writes the promise the port keeps, and it is narrower than the one
  this behaviour was justified by. Its check over the offered list fails on `FolderUnknownError`
  alone and passes over a `MailboxError`, so a listed mailbox that is closed is outside the promise
  by decision. The earlier claim that every name offered opens was therefore never true, and it was
  untrue against the probe itself: `Guarded` is unflagged, is offered, and is refused `[NOPERM]
  Permission denied`. `_opens` is now `_kept_after_opening` and drops a flagged name only on the
  reading `_select` uses, both calling one new `_says_folder_missing`. Nothing observable moves on
  either server. Three mutations over the email package's unit suite, 125 tests, proved the change
  able to fail; it went in with the module contract and runbook corrections the same reading
  forced, and the rule is ADR-0056 decision 8.
