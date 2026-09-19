# Two names the Bridge lists and opens are now withheld, and nobody has looked

**Status:** done 2026-08-21
**Area:** email-confirmer
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

`list_folders` now drops every name a server flags `\Noselect`. That decision was measured against
Dovecot, where the flagged name really is unusable. The ProtonMail Bridge is the other server, and
there the same flag sits on `Folders` and `Labels`, two parents that select cleanly: the earlier
live pass over the whole folder list found every listed name openable, which is the fact recorded
in [docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md). So on the Bridge
this filter withholds two names that worked.

Nothing becomes unreachable, because the children of both are listed under them in their own right,
and what is lost is the ability to search a container whose only content is its children. That is
very probably worth less than the loop the filter closes, and "very probably" is the whole of the
evidence: no live pass has been run against the Bridge since.

Closing it needs one live run and a decision. `test_email_live.py`'s folder test needs the Bridge
and an exported `~/.cortex/email.env` (the procedure is in `docs/runbooks/email-imap.md`), and its
`-k folder` half already asserts that every name `list_folders` returns opens; what it does not
assert is which names it stopped returning. Run it, record what the list holds now, and choose
between leaving the filter as it is and asserting the new list, narrowing it to names that are
flagged and have children, or treating a `\Noselect` name that opens as a mailbox, which costs a
SELECT per listed name.

## History

- 2026-08-21: Filed by the close of [364](364-list-folders-offers-a-name-no-mailbox-has.md), whose
  measurement was against one of the two servers this repo talks to. Recorded in ADR-0056
  decision 8.
- 2026-08-21: Measured against the live Bridge, and the claim held: nineteen names listed, two of
  them flagged `\Noselect` (`Folders` and `Labels`), and all nineteen open under EXAMINE. The flags
  and the per-name SELECT results are in
  [docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md). A fourth ending
  was taken rather than the three this entry weighed: `list_folders` opens a flagged name once on
  the connection it already holds and drops it only when the server refuses it too, which is
  correct on both servers and costs two round trips on this account and none on a server that flags
  nothing. `test_email_live.py` now walks the server's own LIST and asserts the offered list is
  exactly the names that open, which is the assertion that would have caught this the day the
  filter was added. Opened [375](375-a-flagged-name-shut-is-dropped-as-if-missing.md), on the one
  asymmetry this leaves, and [376](376-the-bridge-flag-reading-is-one-account.md), on the reading
  being one account's.
