# `list_folders` offers a name that is not a mailbox, and a refusal sends the model back to it

**Status:** done 2026-08-21
**Area:** email-confirmer
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

`list_folders` returns every name the server lists, and a server may list a name that is only a
node in the hierarchy: a `\Noselect` parent, which has children and is not itself a mailbox.
Dovecot 2.3.21 lists one and then answers a `SELECT` of it with `Mailbox doesn't exist: Parent`,
word for word what it answers for a name no mailbox has, so `ImapMailbox` types it
`FolderUnknownError` and the message tells the model the name comes word for word from
`list_folders`. It did.

It does not happen on the Bridge, whose two `\Noselect` parents (`Folders`, `Labels`) both select
cleanly, which is why the first live pass over the whole folder list found nothing. It is measured
on the probe instead (`test_a_listed_node_that_is_not_a_mailbox_is_refused_as_missing_here` in
`test_imap_probe_live.py`).

The refusal contains nothing that could tell a hierarchy node from a missing folder, so the
classification cannot fix this and the fix belongs one call away, in `list_folders`. imap-tools'
`folder.list()` returns a `FolderInfo` per name with the server's own LIST flags, and the adapter
throws everything but `.name` away. Two options: drop every name flagged `\Noselect` from what
`list_folders` answers, which keeps the port's `Sequence[str]` and is what `FOLDER_HELP` already
promises a model; or pass selectability across the port so a caller can see the tree, which is a
wider port change.

## History

- 2026-08-21: Filed by the close of [327](327-the-other-no-to-select-is-unseen.md), which ran a
  second IMAP server to settle what a refused SELECT means and measured this beside it. Recorded in
  ADR-0057 decision 1.
- 2026-08-21: Done as the first of the two options. imap-tools keeps the server's LIST attributes
  on the `FolderInfo` it builds, so the fact was available at the one call that needed it, and
  `ImapMailbox.list_folders` now drops any name flagged `\Noselect` or `\NonExistent`. The port's
  shape is unchanged and its promise is wider: every name it answers with is one the other two
  calls may be given, checked by two contract cases the fake, the adapter and the live probe all
  run. The rule was later narrowed and is now ADR-0056 decision 8. Opened
  [373](373-a-flag-read-from-a-standard-not-a-server.md), on the second flag being read from a
  standard rather than from a server, and
  [374](374-two-names-the-bridge-lists-are-now-withheld.md), on the two Bridge names this filter
  now withholds.
