# The other kind of refused SELECT has never been seen on a server this repo can reach

**Status:** landed 2026-08-21
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-19 by the close of [318](318-a-folder-refusal-is-untyped.md), which typed a folder
no mailbox has and could measure only half of the question it was given. A `NO` to `SELECT` covers
two facts, a mailbox that does not exist and a mailbox that does and cannot be opened, and only
the first was ever produced. Against the live Bridge every wrong name is refused identically, with
the words `no such mailbox` and no RFC 5530 response code beside them, while every one of the
nineteen folders the account lists opens cleanly, the two `\Noselect` parents (`Folders`,
`Labels`) included. So the contrast case has no live example anywhere in this repo.

What landed is safe rather than complete. `_FOLDER_MISSING_ANSWERS` matches on presence, the
measured phrase or the standard's `[NONEXISTENT]` code, so a refusal that says neither stays a
plain `MailboxError` and a folder that cannot be proved missing is never reported missing. The
cost of the gap is not a wrong answer, it is that the fail-safe branch is exercised only from a
scripted stub (`UNOPENABLE_FOLDER_ANSWER`, RFC 5530's `[INUSE]`), which is a sentence this repo
wrote about a server it has never met. Two things follow. The rule rests on one server's English
wording, so a Bridge that reworded its `NO` would silently stop typing the common case, which the
live test would catch only because it asserts the type. And nothing has ever confirmed that a real
"exists but unavailable" refusal fails to match either signal, which is the assumption the safety
argument is built on.

**What would close it.** A second IMAP server, run locally for the purpose (a Dovecot container is
the obvious one, and it can be made to hold a `\Noselect` parent and an ACL-denied mailbox that a
Bridge account cannot), driven through `ImapMailbox` to record what each of the two situations
really answers. Then either the classification stands as measured, with the second server's
wording added where it agrees, or it moves to whatever machine-readable signal both servers turn
out to share. The outcome is worth writing down even if nothing changes, because "we looked and
the phrase is all there is" is a different state from "we never looked".

## Trail

- 2026-08-19: Opened by the close of [318](318-a-folder-refusal-is-untyped.md), which measured the
  missing-folder refusal against a real Bridge, could not construct its contrast case on any
  server it could reach, and chose the fail-safe classification rather than guessing at one.
- 2026-08-21: Closed by running one. `docker/docker-compose.imap-probe.yml` starts a
  `dovecot/dovecot:2.3.21` with its ACL plugin on over the tree
  `docker/dovecot/probe-mailboxes.sh` builds, four listed names of which one is listed, real and
  shut, and `test_imap_probe_live.py` drives `ImapMailbox` over it (`just up-imap-probe`,
  `just email-folder-probe`). Both halves are now measurements. The refusal for a mailbox that is
  there and shut reads `[NOPERM] Permission denied` and carries neither measured phrase nor
  `[NONEXISTENT]`, so the assumption the safety argument rested on holds against a server that
  really sends one, and the scripted answer both suites drive that branch with is that sentence
  rather than an invented `[INUSE]`. The classification stands and gains a phrase: this server
  says a folder is missing with `Mailbox doesn't exist`, sharing no word with the Bridge's
  `no such mailbox`, and neither server sends a response code with it, so the alternative of
  moving to a machine-readable signal both share is not available. `_FOLDER_MISSING_ANSWERS` holds
  both measured phrases beside the standard's code. Written up in the ADR-0022 two-server
  addendum, with the verbatim answers there and in the runbook. Two things measured on the way
  past are filed rather than fixed here:
  [364](364-list-folders-offers-a-name-no-mailbox-has.md), a listed `\Noselect` node this server
  refuses in the words that prove a folder missing, and
  [365](365-a-refused-name-is-neither-missing-nor-shut.md), a third fact the same `NO` carries.
  The fixture's own names, spelled in its script and in its test with nothing tying them, are
  [366](366-the-probe-fixture-and-its-test-are-untied.md).
