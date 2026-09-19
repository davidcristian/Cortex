# The `search_emails` query dialect

**Status:** done 2026-08-18
**Area:** email-confirmer
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

`query` is passed to imap-tools unaltered, so the dialect is raw IMAP `SEARCH` criteria, and the tool
said only "an IMAP query". A model that writes `from:someone@example.com` is writing the search
syntax of every mail client a person has ever used, and that is not the dialect here; the refusal
comes back from the IMAP server as a `BAD`, which is a wasted dispatch and a reply the model cannot
repair without knowing the grammar.

It was not closed with the attachment fields because an accurate description is a list of criteria
that work, and this repo had run exactly two against a real ProtonMail Bridge, `ALL` and
`SUBJECT "..."`. Copying a longer list out of the RFC would advertise a capability nobody here had
run, against a server whose `SEARCH` support is partial by reputation.

## History

- 2026-08-11: Opened by the review that closed the per-field attachment schema descriptions.
- 2026-08-18: Closed. The live pass ran read-only against Proton Mail Bridge 03.25.00 through this
  repo's own `ImapMailbox`, over a folder of 1205 messages, and every criterion the entry named
  works: the dates partition the folder cleanly, `FROM` and the other quoted-argument criteria
  discriminate, `UNSEEN` answers, and `OR`, `NOT`, juxtaposition and parentheses compose. The
  refusals matter as much: the client `from:` syntax, an ISO date and an unquoted multi-word argument
  are each rejected by the server, and `KEYWORD` was refused for the flag it was tried with, so it is
  not named. `values.py` now has the description for `query`, and for `folder` and `limit`; an
  integration-marked test runs one query per named group of criteria and fails if the prose ever
  names a criterion no query ran ([ADR-0056](../../adr/ADR-0056-email-reader-answers.md) decision 1).
  What escapes on a query the server still refuses is the IMAP library's own error, filed as
  [312](312-search-refusal-is-untyped.md).
