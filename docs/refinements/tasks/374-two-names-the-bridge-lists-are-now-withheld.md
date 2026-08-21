# Two names the Bridge lists and opens are now withheld, and nobody has looked

**Status:** open, actionable
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-21 by the close of [364](364-list-folders-offers-a-name-no-mailbox-has.md), which
made `list_folders` drop every name a server flags `\Noselect`. That decision was measured against
Dovecot, where the flagged name really is unusable. The ProtonMail Bridge is the other server, and
there the same flag sits on `Folders` and `Labels`, two parents that select cleanly: the earlier
live pass over the whole folder list found every listed name openable, which is the fact recorded
in the ADR-0022 two-server addendum. So on the Bridge this filter withholds two names that worked.

Nothing about the tree becomes unreachable, because the children of both are listed under them in
their own right, and what is lost is the ability to search a container whose only content is its
children. That is very probably worth less than the loop the filter closes, which is why it landed
that way. But "very probably" is the whole of the evidence: no live pass has been run against the
Bridge since, so what the model is now offered there is inferred rather than seen.

**What would close it.** One live run and a decision. `test_email_live.py`'s folder test needs the
Bridge and an exported `~/.cortex/email.env` (the procedure is in `docs/runbooks/email-imap.md`),
and its `-k folder` half already asserts that every name `list_folders` returns opens; what it does
not assert is which names it stopped returning. Run it, record what the list holds now, and decide
between three endings: leave the filter as it is and pin the new list, narrow it to names that are
flagged and have children, or make the promise a per-name one by treating a `\Noselect` name that
opens as a mailbox, which costs a SELECT per listed name and is the option the close rejected on
cost rather than on principle. The sibling entry
[373](373-a-flag-read-from-a-standard-not-a-server.md) is the same shape of gap on the other flag.

## Trail

- 2026-08-21: Filed by the close of [364](364-list-folders-offers-a-name-no-mailbox-has.md), whose
  measurement was against one of the two servers this repo talks to. Recorded in the ADR-0022
  hierarchy-node addendum.
