# The answer the folder rule reads holds the name the caller sent

**Status:** open, fix when it bites
**Area:** email-confirmer
**Trigger:** a third IMAP server, or one whose refusal for a mailbox that is there and shut echoes
the name it refused. The first limb is read off the compose files, which name every server image
this repo runs (`grep -n 'image:' docker/*.yml`); the second by shutting a mailbox on a server this
repo reaches and reading the refusal verbatim. On the probe that reading can move only when its
image line or `docker/dovecot/` changes, and it is taken after `just up-imap-probe` by an EXAMINE
of `Guarded`, the mailbox there and shut, past the port. The Bridge limb needs a live run against the
account. This entry's trail records both readings.
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-09-17

`select` in `brain/packages/email/src/cortex_email/folders.py` classifies a refused SELECT through
`_says_folder_missing`, which lower-cases `str(err)` and looks for a measured phrase or an RFC 5530
code anywhere in it. That string is
what imap-tools rendered out of the refused command, and a server that names the mailbox it refused
puts the caller's own folder name inside it: Dovecot answers `Mailbox doesn't exist: <name>`. So a
caller supplies part of the text the classification reads, and a folder named `[NOPERM] archive` or
`no such mailbox` is a name whose refusal carries the rule's own needles.

Today this is harmless on both servers the repo talks to, and it was measured rather than assumed.
The echo really happens, verbatim from the probe:

    EXAMINE "[NOPERM] archive"   NO Mailbox doesn't exist: [NOPERM] archive (0.001 + 0.000 secs).
    EXAMINE "no such mailbox"    NO Mailbox doesn't exist: no such mailbox (0.001 + 0.000 secs).
    EXAMINE "[CANNOT] thing"     NO Mailbox doesn't exist: [CANNOT] thing (0.001 + 0.000 secs).

The direction that could cause harm is the fail-safe one, a mailbox that is really there and shut
being reported missing, and reaching it needs a refusal that both declines a real mailbox and
echoes the name. Dovecot's is `[NOPERM] Permission denied` with no name in it, and the Bridge
cannot produce a shut mailbox at all. In the other direction the echo changes nothing: a name no
mailbox has is answered `Mailbox doesn't exist: <name>` whatever the name is, so the phrase that
matches is the server's own either way.

That harmful direction was built on 2026-09-08 rather than reasoned about. The probe was given a
real mailbox named `no such mailbox` and shut with the same ACL that shuts `Guarded`, which is the
worst name this rule can be handed: a mailbox that is there, cannot be opened, and is called the
needle. The server refused it `NO [NOPERM] Permission denied (0.001 + 0.000 secs).` with the name
nowhere in the answer, and the port raised the base `MailboxError` rather than `FolderUnknownError`.
`Parent`, once the same ACL shut it, was refused in exactly those words too. So this server's shut
refusal carries no mailbox name whatever the mailbox is called, and the echo it does produce belongs
to the direction that changes nothing.

**What would close it.** Reading the response code and the text out of the refused command's data
rather than out of a rendered exception message, which is where the boundary between what the
server said and what the caller sent actually is. imap-tools 1.13.0 carries the raw `(status, data)`
on `MailboxFolderSelectError` as `command_result`, inherited from `UnexpectedCommandStatusError`,
whose `__str__` is what renders it into the message the rule reads today; so the parse is available
without reaching past the library. What has to be decided is how much of an IMAP response-code
grammar to write for a needle that is currently one `in` against a string. The cheaper half, and
the one worth doing first if this ever bites, is to stop matching anywhere in the message and match
only at the front of the first data line, `err.command_result[1][0]`, for the phrases as well as
the codes. Anchoring the codes alone would not close this: the echoed name follows the phrase, so a
phrase needle matched anywhere still reads the name. Every refusal measured so far puts its
evidence first and the name after it (`Mailbox doesn't exist: <name>`, `no such mailbox`,
`[NOPERM] Permission denied`, `[CANNOT] Invalid mailbox name: ...`), and the front is also the one
position RFC 5530 lets a code appear in.

## Trail

- 2026-09-07: trigger swept and not fired, on both limbs. This repo reaches two IMAP servers and
  no third: the ProtonMail Bridge the live suite talks to, and the probe's dovecot, which is the
  only IMAP server image any compose file here names. The refusal dovecot gives for a mailbox that
  is there and shut is `NO [NOPERM] Permission denied (0.001 + 0.000 secs).`, asserted in
  `brain/packages/email/tests/test_imap_probe_live.py` and recorded in the runbook's table of
  measured answers, and it carries no mailbox name; the echo happens only in the refusal for a
  name no mailbox has, which is the harmless direction this entry already measured. The Bridge
  still cannot produce a shut mailbox at all, read live today: every one of the 19 names it lists
  opens. Recorded in the ADR-0022 trigger-sweep addendum.
- 2026-09-08: read again on both limbs, neither fired, and the second was measured rather than
  inferred. `grep -n 'image:' docker/*.yml` returns one IMAP server image, `dovecot/dovecot:2.3.21`,
  so this repo still reaches two servers and no third. The echo reproduced verbatim on the probe the
  same day, the three lines above plus `EXAMINE "Nonexistent"` answered
  `NO Mailbox doesn't exist: Nonexistent (0.001 + 0.000 secs).`, and the harmful direction was then
  built: a real mailbox named `no such mailbox`, ACL-shut, refused
  `NO [NOPERM] Permission denied (0.001 + 0.000 secs).` with no name in it and raised the base
  `MailboxError` through the port. The Bridge was read live the same day and still refuses nothing
  at all, 19 names listed and 19 opening. The library claim in **What would close it** was checked
  against the installed imap-tools 1.13.0 rather than taken on trust:
  `MailboxFolderSelectError` inherits `UnexpectedCommandStatusError`, which stores the refused
  command's `(status, data)` as `command_result` and renders it into `__str__` as `Data: ...`, so
  the raw tuple really is on the exception the adapter already catches. Recorded in the ADR-0022
  addendum of the same day.
- 2026-09-09: claims held against the code and the trigger read again on both limbs, neither
  fired. `grep -n 'image:' docker/*.yml` still returns one IMAP server image,
  `dovecot/dovecot:2.3.21`, so this repo still reaches two servers and no third. The Bridge was read
  live today and refuses no listed name, 19 listed and 19 opening, so it produces no shut refusal to
  echo a name. The library claim was rechecked in the installed imap-tools 1.13.0:
  `MailboxFolderSelectError` inherits `UnexpectedCommandStatusError`, whose `__init__` binds the
  refused command's `(status, data)` as `command_result` and whose `__str__` renders it as
  `Data: ...`.
- 2026-09-12: claims held against the code and both limbs read again, neither fired.
  `grep -n 'image:' docker/*.yml` still returns one IMAP server image, `dovecot/dovecot:2.3.21`, so
  this repo still reaches two servers and no third. The echo was reproduced on the probe rather
  than quoted: `EXAMINE "[NOPERM] archive"` answered `NO Mailbox doesn't exist: [NOPERM] archive
  (0.001 + 0.000 secs).`, and `"no such mailbox"`, `"[CANNOT] thing"` and `"Nonexistent"` the same
  way, while `Guarded`, the mailbox that is there and shut, was refused `NO [NOPERM] Permission
  denied (0.001 + 0.000 secs).` with no name in it. So the echo is still confined to the direction
  that changes nothing. The library claim was rechecked in the installed imap-tools 1.13.0:
  `MailboxFolderSelectError` inherits `UnexpectedCommandStatusError`, whose `__init__` binds the
  refused command's `(status, data)` as `command_result` and whose `__str__` renders it as
  `Data: ...`. The Bridge was not read today, the slot ruling out a live run against it. One thing
  did move under this entry without changing it: the reading `_select` does is now a named
  predicate, `_says_folder_missing`, shared with the listing's own filter
  ([375](375-a-flagged-name-shut-is-dropped-as-if-missing.md)). It reads the same rendered message
  the same way, so **What would close it** is unchanged except that the parse would now land in one
  place instead of two.
- 2026-09-17: claims held against the code, both limbs read, neither fired, and the closing move is
  corrected. The classification moved on 2026-09-15 from `imap.py` to
  `brain/packages/email/src/cortex_email/folders.py`, where `_select` is now the public `select`;
  `_says_folder_missing` and `_FOLDER_MISSING_ANSWERS` moved with it unchanged, which an AST
  comparison of the two versions confirmed. The send-side rework of the same week (`drafts.py`,
  `SendError`) and the tool audit file sink touched neither. `grep -n 'image:' docker/*.yml` still
  returns one IMAP server image, `dovecot/dovecot:2.3.21`. The probe was started and read past the
  port: `EXAMINE "[NOPERM] archive"` answered `('NO', [b"Mailbox doesn't exist: [NOPERM] archive
  (0.001 + 0.000 secs)."])`, and `"no such mailbox"`, `"[CANNOT] thing"` and `"Nonexistent"` the
  same way, while `Guarded` was refused `[NOPERM] Permission denied (0.001 + 0.000 secs).` with no
  name in it, and the probe's live suite passed 9 of 9. The library claim held in the installed
  imap-tools 1.13.0, whose `__str__` renders `command_result[1]` as a Python list after `Data: `.
  The Bridge was not read, so its limb is carried over from 2026-09-09. The correction: the cheaper
  half used to anchor only the code, which leaves the phrase needle free to match the echoed name,
  so it now anchors both.
