# The `search_emails` query dialect

**Status:** landed 2026-08-18
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

The `search_emails` query dialect is unstated (opened 2026-08-11 by the sibling sweep in the
[ADR-0022 per-field addendum](../../adr/ADR-0022-email-write-confirmer.md); the read tools are
[ADR-0009](../../adr/ADR-0009-tools-mcp.md)'s). `query` is passed to imap-tools unaltered, so the
dialect is raw IMAP `SEARCH` criteria, and the tool says only "an IMAP query". A model that writes
`from:someone@example.com` is writing the search syntax of every mail client a person has ever used,
and that is not the dialect here; the refusal comes back from the IMAP server as a `BAD`, which is a
wasted dispatch and a reply the model cannot repair without knowing the grammar. It is not closed
with the attachment fields because an accurate description is a list of criteria that **work**, and
this repo has run exactly two against a real ProtonMail Bridge, `ALL` and `SUBJECT "..."`, being the
two the live round-trip uses. Copying a longer list out of the RFC would advertise a capability
nobody here has run, against a server whose `SEARCH` support is partial by reputation.

## Trail

- 2026-08-11: opened by the sibling sweep that closed the per-field attachment schema descriptions,
  and it took that entry's place in the fix-when-it-bites bucket the same day, so the area count
  held at 4 rather than falling.
- 2026-08-11: the index states the trigger with a second arm the entry's own text does not carry,
  namely a deployment observed failing a search, offered beside the one live pass over the criteria
  worth naming.
- 2026-08-18: Landed. The live pass ran read-only against Proton Mail Bridge 03.25.00 through this
  repo's own `ImapMailbox`, over a folder of 1205 messages, and every criterion the entry named
  works: the dates partition the folder cleanly, `FROM` and the other quoted-argument criteria
  discriminate, `UNSEEN` answers, and `OR`, `NOT`, juxtaposition and parentheses compose. The
  refusals matter as much: the client `from:` syntax, an ISO date and an unquoted multi-word
  argument are each rejected by the server, and `KEYWORD` was refused for the flag it was probed
  with, so it is not named. `values.py` now carries the description for `query`, and for the two
  sibling guesses in the same tools, `folder` and `limit`; an integration-marked test runs one query
  per named group of criteria and fails if the prose ever names a criterion no query ran. ADR-0022
  carries the dated addendum. What escapes on a query the server still refuses is the IMAP library's
  own error, which is filed as [312](312-search-refusal-is-untyped.md).
