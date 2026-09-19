# The refusal the folder rule reads can contain the name the caller sent

**Status:** open, waiting for its trigger
**Area:** email-confirmer
**Trigger:** a third IMAP server, or one whose refusal for a mailbox that exists but is closed
repeats the name it refused. The first part is read off the compose files, which name every server
image this repo runs (`grep -n 'image:' docker/*.yml`); the second by closing a mailbox on a server
this repo reaches and reading the refusal verbatim. On the probe that reading can change only when
its image line or `docker/dovecot/` changes, and it is taken after `just up-imap-probe` by an
EXAMINE of `Guarded`, the mailbox there that is closed, through the port. The Bridge part needs a
live run against the account. The history below records both readings.
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)
**Verified:** 2026-09-19

`select` in `brain/packages/email/src/cortex_email/folders.py` classifies a refused SELECT with
`_says_folder_missing`, which lower-cases `str(err)` and looks for a measured phrase or an
RFC 5530 code anywhere in it. That string is what imap-tools rendered from the refused command,
and a server that repeats the mailbox it refused puts the caller's own folder name inside it:
Dovecot answers `Mailbox doesn't exist: <name>`. So a folder named `[NOPERM] archive` or
`no such mailbox` produces a refusal containing the text the rule searches for.

This is harmless on both servers the repo talks to, and that was measured rather than assumed. The
repetition does happen, verbatim from the probe:

    EXAMINE "[NOPERM] archive"   NO Mailbox doesn't exist: [NOPERM] archive (0.001 + 0.000 secs).
    EXAMINE "no such mailbox"    NO Mailbox doesn't exist: no such mailbox (0.001 + 0.000 secs).
    EXAMINE "[CANNOT] thing"     NO Mailbox doesn't exist: [CANNOT] thing (0.001 + 0.000 secs).

Harm needs the other direction: a mailbox that is really there and closed being reported missing.
Dovecot refuses those with `[NOPERM] Permission denied` and no name in it, and the Bridge has no
closed mailbox at all. That direction was built on 2026-09-08 rather than reasoned about: the probe
was given a real mailbox named `no such mailbox`, closed with the same ACL as `Guarded`, which is
the worst name this rule can be handed. The server refused it
`NO [NOPERM] Permission denied (0.001 + 0.000 secs).` with the name nowhere in the answer, and the
port raised the base `MailboxError` rather than `FolderUnknownError`. `Parent`, once the same ACL
closed it, was refused in exactly those words too.

**What would close it.** Read the response code and text out of the refused command's data instead
of out of a rendered exception message, which is where the boundary between what the server said
and what the caller sent actually is. imap-tools 1.13.0 keeps the raw `(status, data)` on
`MailboxFolderSelectError` as `command_result`, inherited from `UnexpectedCommandStatusError`,
whose `__str__` renders it into the message the rule reads today, so the parse needs nothing
beyond the library. What has to be decided is how much of an IMAP response-code grammar to write
for what is currently one `in` against a string. The cheaper half is to stop matching anywhere in
the message and match only at the start of the first data line, `err.command_result[1][0]`, for
the phrases as well as the codes. Anchoring the codes alone would not close this, because the
repeated name follows the phrase. Every refusal measured so far puts its evidence first and the
name after it (`Mailbox doesn't exist: <name>`, `no such mailbox`, `[NOPERM] Permission denied`,
`[CANNOT] Invalid mailbox name: ...`), and the start of the line is also the only position
RFC 5530 allows a code.

## History

- 2026-09-07: trigger checked on both parts, neither fired. This repo reaches two IMAP servers and
  no third: the ProtonMail Bridge the live suite talks to, and the probe's dovecot, the only IMAP
  server image any compose file here names. Dovecot's refusal for a mailbox that is there and
  closed is `NO [NOPERM] Permission denied (0.001 + 0.000 secs).`, checked in
  `brain/packages/email/tests/test_imap_probe_live.py` and recorded in the runbook's table of
  measured answers, and it contains no mailbox name. The Bridge still has no closed mailbox: all
  19 names it lists opened.
- 2026-09-08: read again on both parts, neither fired, and the second was measured.
  `grep -n 'image:' docker/*.yml` returns one IMAP server image, `dovecot/dovecot:2.3.21`. The
  repetition reproduced verbatim on the probe, the three lines above plus `EXAMINE "Nonexistent"`
  answered `NO Mailbox doesn't exist: Nonexistent (0.001 + 0.000 secs).`, and the harmful
  direction was then built with the result described above. The Bridge listed 19 names and all 19
  opened. The library claim was checked against the installed imap-tools 1.13.0:
  `MailboxFolderSelectError` inherits `UnexpectedCommandStatusError`, which stores the refused
  command's `(status, data)` as `command_result` and renders it into `__str__` as `Data: ...`.
- 2026-09-09: claims checked against the code and the trigger read again on both parts, neither
  fired. Still one IMAP server image. The Bridge was read live and refuses no listed name, 19
  listed and 19 opening. The library claim was rechecked in imap-tools 1.13.0.
- 2026-09-12: claims checked and both parts read again, neither fired. Still one IMAP server
  image. The repetition was reproduced rather than quoted: `EXAMINE "[NOPERM] archive"` answered
  `NO Mailbox doesn't exist: [NOPERM] archive (0.001 + 0.000 secs).`, and `"no such mailbox"`,
  `"[CANNOT] thing"` and `"Nonexistent"` the same way, while `Guarded` was refused
  `NO [NOPERM] Permission denied (0.001 + 0.000 secs).` with no name in it. The library claim was
  rechecked. The Bridge was not read, the slot ruling out a live run. One thing moved under this
  entry without changing it: the reading `_select` does is now a named predicate,
  `_says_folder_missing`, shared with the listing's own filter
  ([375](375-a-flagged-name-shut-is-dropped-as-if-missing.md)). It reads the same rendered message
  the same way, so the parse above would now go in one place instead of two.
- 2026-09-17: claims checked, both parts read, neither fired, and the closing move is corrected.
  The classification moved on 2026-09-15 from `imap.py` to
  `brain/packages/email/src/cortex_email/folders.py`, where `_select` is now the public `select`;
  `_says_folder_missing` and `_FOLDER_MISSING_ANSWERS` moved with it unchanged, confirmed by an
  AST comparison of the two versions. The send-side rework of the same week (`drafts.py`,
  `SendError`) and the tool audit file sink touched neither. Still one IMAP server image. The
  probe was started and read through the port: `EXAMINE "[NOPERM] archive"` answered
  `('NO', [b"Mailbox doesn't exist: [NOPERM] archive (0.001 + 0.000 secs)."])`, and
  `"no such mailbox"`, `"[CANNOT] thing"` and `"Nonexistent"` the same way, while `Guarded` was
  refused `[NOPERM] Permission denied (0.001 + 0.000 secs).` with no name in it, and the probe's
  live suite passed 9 of 9. The library claim held in imap-tools 1.13.0, whose `__str__` renders
  `command_result[1]` as a Python list after `Data: `. The Bridge was not read, so its part is
  still the reading of 2026-09-09. The correction: the cheaper half used to anchor only the code,
  which leaves the phrase free to match the repeated name, so it now anchors both.
- 2026-09-19: claims checked against the code, neither part fired, and the probe was not started.
  `folders.py` has no commit since it was split out on 2026-09-15, so `select` still raises
  `FolderUnknownError` when `_says_folder_missing` finds a match anywhere in the lower-cased
  `str(err)`, and the installed imap-tools is still 1.13.0. Still one IMAP server image, and the
  local image resolves to the digest recorded in
  [docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md),
  `sha256:1c18c756f20d03867077a1b509a6e2e3008ab1eafa56377b6f2eca12dc1ba581`. By this entry's own
  rule the probe's reading changes only with that image line or `docker/dovecot/`, and neither has
  a commit since 2026-09-05, so the reading of 2026-09-17 still applies without a restart. The
  Bridge part is still the reading of 2026-09-09, tonight's run having ruled out a live run
  against the account.
