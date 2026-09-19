# The other kind of refused SELECT has never been seen on a server this repo can reach

**Status:** done 2026-08-21
**Area:** email-confirmer
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

A `NO` to `SELECT` covers two facts, a mailbox that does not exist and a mailbox that does and
cannot be opened, and only the first was ever produced. Against the live Bridge every wrong name is
refused identically, with the words `no such mailbox` and no RFC 5530 response code, while every
one of the nineteen folders the account lists opens cleanly, the two `\Noselect` parents
(`Folders`, `Labels`) included. So the contrasting case had no live example anywhere in this repo.

What was built is safe rather than complete. `_FOLDER_MISSING_ANSWERS` matches on presence, the
measured phrase or the standard's `[NONEXISTENT]` code, so a refusal that says neither stays a
plain `MailboxError` and a folder that cannot be proved missing is never reported missing. The cost
is that the safe branch was exercised only from a scripted stub (`UNOPENABLE_FOLDER_ANSWER`, RFC
5530's `[INUSE]`), a sentence this repo wrote about a server it had never met. Two things follow.
The rule rests on one server's English wording, so a Bridge that reworded its `NO` would stop
typing the common case. And nothing had confirmed that a real "exists but unavailable" refusal
fails to match either signal, which is the assumption the safety argument is built on.

Closing it needs a second IMAP server, run locally, holding a `\Noselect` parent and an ACL-denied
mailbox, driven through `ImapMailbox` to record what each situation really answers.

## History

- 2026-08-19: Opened by the close of [318](318-a-folder-refusal-is-untyped.md), which measured the
  missing-folder refusal against a real Bridge, could not construct its contrasting case on any
  server it could reach, and chose the safe classification rather than guessing.
- 2026-08-21: Closed by running one. `docker/docker-compose.imap-probe.yml` starts a
  `dovecot/dovecot:2.3.21` with its ACL plugin on over the tree
  `docker/dovecot/probe-mailboxes.sh` builds, four listed names of which one is listed, real and
  closed, and `test_imap_probe_live.py` drives `ImapMailbox` over it (`just up-imap-probe`,
  `just email-folder-probe`). Both halves are measurements now. The refusal for a mailbox that is
  there and closed reads `[NOPERM] Permission denied` and contains neither measured phrase nor
  `[NONEXISTENT]`, so the assumption the safety argument rested on holds against a server that
  really sends one, and the scripted answer both suites use for that branch is that sentence rather
  than an invented `[INUSE]`. The classification stands and gains a phrase: this server says a
  folder is missing with `Mailbox doesn't exist`, sharing no word with the Bridge's `no such
  mailbox`, and neither server sends a response code with it, so moving to a machine-readable
  signal both share is not available. `_FOLDER_MISSING_ANSWERS` holds both measured phrases beside
  the standard's code. Written up in ADR-0056 decision 6, with the answers word for word in
  [docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md) and in the runbook.
  Two things measured on the way are filed rather than fixed here:
  [364](364-list-folders-offers-a-name-no-mailbox-has.md), a listed `\Noselect` node this server
  refuses in the words that prove a folder missing, and
  [365](365-a-refused-name-is-neither-missing-nor-shut.md), a third fact the same `NO` conveys. The
  fixture's own names, written in its script and in its test with nothing comparing them, are
  [366](366-the-probe-fixture-and-its-test-are-untied.md).
