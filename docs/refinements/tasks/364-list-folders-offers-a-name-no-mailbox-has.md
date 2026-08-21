# `list_folders` offers a name that is not a mailbox, and a refusal sends the model to it

**Status:** open, actionable
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-21 by the close of [327](327-the-other-no-to-select-is-unseen.md), which ran a
second IMAP server and found this on the way past. `list_folders` returns every name the server
lists, and a server may list a name that is only a node in the hierarchy: a `\Noselect` parent,
which has children and is not itself a mailbox. Dovecot 2.3.21 lists one and then answers a
`SELECT` of it with `Mailbox doesn't exist: Parent`, word for word what it answers for a name no
mailbox has, so `ImapMailbox` types it `FolderUnknownError` and the message tells the model the
name comes verbatim from `list_folders`. It did. That is the loop the fail-safe classification
exists to avoid, arriving from the other side: not a refusal read wrongly but a list offering a
name that was never usable.

It does not happen on the Bridge, whose two `\Noselect` parents (`Folders`, `Labels`) both select
cleanly, which is why the first live pass over the whole folder list found nothing. It is measured
and pinned on the probe instead (`test_a_listed_node_that_is_not_a_mailbox_is_refused_as_missing_here`
in `test_imap_probe_live.py`), so the fact is recorded rather than latent.

**What would close it.** The refusal carries nothing that could tell a hierarchy node from a
missing folder, so the classification cannot fix this and the fix belongs one call away, in
`list_folders`. imap-tools' `folder.list()` returns a `FolderInfo` per name carrying the server's
own LIST flags, and the adapter already throws everything but `.name` away. Two shapes are worth
weighing before either is built: dropping every name flagged `\Noselect` from what `list_folders`
answers, which keeps the port's `Sequence[str]` and is what `FOLDER_HELP` already promises a model
(the names it may use), against carrying selectability across the port so a caller can see the
tree, which is a port change and a wider one than this needs. Whichever wins, the fake and the
contract need the same shape, and the probe is already standing by to prove it against a server
that really lists one.

## Trail

- 2026-08-21: Filed by the close of [327](327-the-other-no-to-select-is-unseen.md), which ran a
  second IMAP server to settle what a refused SELECT means and measured this beside it: that
  server lists a `\Noselect` node and refuses it in the words that prove a folder missing.
  Recorded in the ADR-0022 two-server addendum.
