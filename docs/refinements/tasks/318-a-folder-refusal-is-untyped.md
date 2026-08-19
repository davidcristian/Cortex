# A folder no mailbox has reaches the model as the IMAP library's own sentence

**Status:** open, actionable
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-19 by the close of [312](312-search-refusal-is-untyped.md), which gave a refused
query its own type and stopped there on purpose. `folder` is the sibling guess in the same two
tools, described just as carefully (`FOLDER_HELP` says the name comes verbatim from
`list_folders` and that an invented one is an error rather than an empty result, measured live as
`no such mailbox`), and it is the cheaper of the two to get wrong: `list_folders` is one call
away.

What comes back is now typed but not shaped. `box.folder.set` raises imap-tools'
`MailboxFolderSelectError` for a `NO` to `SELECT`, which `ImapMailbox` wraps as the base
`MailboxError`, so the model reads `Error executing tool search_emails: the mailbox could not run
that search: Response status "OK" expected, but "NO" received. Data: [b'no such mailbox']`. The
library's type no longer crosses the port, which was the whole of the gate-5 problem, but the
sentence the model reads is still imap-tools describing a command status to a caller who never
sent a command, and the folder it refused is not in the message at all.

**What would close it.** The same design one type further: a `FolderUnknownError` (name it with
the port's family in mind) beside `SearchRefusedError`, raised where the select fails, carrying
the folder it was given and telling the model to call `list_folders` rather than guess again.
Two questions want deciding rather than assuming, both answerable only against a real Bridge. A
`NO` to `SELECT` is not always a missing folder, so what distinguishes "no such mailbox" from a
folder that exists and could not be opened has to be read off the response rather than inferred
from the fact that a select failed; and `read_email` takes a folder too, so whatever is raised
must read sensibly out of both tools. The refused-search slice left the two shared test modules
(`mailbox_fake.py`, `imap_stub.py`) and the port contract (`mailbox_contract.py`) in place, so the
cost here is the classification and its live pass rather than any new scaffolding.

## Trail

- 2026-08-19: Opened by the close of [312](312-search-refusal-is-untyped.md), which typed the
  refused query and deliberately left its sibling to a slice that can measure the Bridge's `NO`
  responses rather than guess at them.
