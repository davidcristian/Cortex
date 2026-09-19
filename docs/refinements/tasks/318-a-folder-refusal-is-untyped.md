# A folder no mailbox has reaches the model as the IMAP library's own sentence

**Status:** done 2026-08-19
**Area:** email-confirmer
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

[312](312-search-refusal-is-untyped.md) gave a refused query its own type and stopped there on
purpose. `folder` is the sibling guess in the same two tools, described just as carefully
(`FOLDER_HELP` says the name comes word for word from `list_folders` and that an invented one is an
error rather than an empty result, measured live as `no such mailbox`), and it is the cheaper of
the two to get wrong, since `list_folders` is one call away.

What came back was typed but not written for the model. `box.folder.set` raises imap-tools'
`MailboxFolderSelectError` for a `NO` to `SELECT`, which `ImapMailbox` wrapped as the base
`MailboxError`, so the model read `Error executing tool search_emails: the mailbox could not run
that search: Response status "OK" expected, but "NO" received. Data: [b'no such mailbox']`. The
library's type no longer crossed the port, but the sentence is still imap-tools describing a
command status to a caller who never sent a command, and the folder it refused is not in the
message.

The fix is the same design one type further: a `FolderUnknownError` beside `SearchRefusedError`,
raised where the select fails, containing the folder it was given and telling the model to call
`list_folders`. Two questions need deciding against a real Bridge rather than assuming. A `NO` to
`SELECT` is not always a missing folder, so what separates "no such mailbox" from a folder that
exists and could not be opened has to be read off the response; and `read_email` takes a folder
too, so whatever is raised must read sensibly out of both tools.

## History

- 2026-08-19: Opened by the close of [312](312-search-refusal-is-untyped.md), which typed the
  refused query and left its sibling to a slice that can measure the Bridge's `NO` responses.
- 2026-08-19: Fixed as `FolderUnknownError` beside `SearchRefusedError`, containing the folder it
  was given and naming `list_folders` as the correction, raised by `ImapMailbox._select` and by the
  fake on the same input, and returned by both folder-taking tools in the port's own words with
  `isError` set. Both questions were taken to a real Bridge: every form of a name no mailbox has is
  refused identically as `no such mailbox` with no RFC 5530 response code, and every folder
  `list_folders` returns opens, so the contrasting case could not be constructed at all. The
  classification therefore matches on what the server said (that phrase or the standard's
  `[NONEXISTENT]`) and everything else stays a plain `MailboxError`, which is the safe direction;
  `read_email` was checked end to end beside `search_emails`, since it fails on the folder before
  it looks at a uid. Written up in ADR-0056 decision 6. That unmeasurable case is now
  [327](327-the-other-no-to-select-is-unseen.md).
