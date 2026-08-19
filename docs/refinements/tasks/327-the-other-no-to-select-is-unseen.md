# The other kind of refused SELECT has never been seen on a server this repo can reach

**Status:** open, actionable
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
