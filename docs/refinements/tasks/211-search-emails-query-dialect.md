# The `search_emails` query dialect

**Status:** open, fix when it bites
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Trigger:** One live pass over the criteria worth naming (dates, `FROM`, `UNSEEN`, `OR`/`NOT`).

The `search_emails` query dialect is unstated (opened 2026-08-11 by the sibling sweep in the
[ADR-0022 per-field addendum](../../adr/ADR-0022-email-write-confirmer.md); the read tools are
[ADR-0009](../../adr/ADR-0009-tools-mcp.md)'s). `query` is passed to imap-tools unaltered, so the
dialect is raw IMAP `SEARCH` criteria, and the tool says only "an IMAP query". A model that
writes `from:someone@example.com` is writing the search syntax of every mail client a person has
ever used, and it is not this one; the refusal comes back from the IMAP server as a `BAD`, which
is a wasted dispatch and a reply the model cannot repair without knowing the grammar. It is not
closed with the attachment fields because an honest description is a list of criteria that
**work**, and this repo has run exactly two against a real ProtonMail Bridge, `ALL` and
`SUBJECT "..."`, being the two the live round-trip uses. Copying a longer list out of the RFC
would advertise a capability nobody here has run, against a server whose `SEARCH` support is
partial by reputation. Its trigger is one live pass over the criteria worth naming (dates,
`FROM`, `UNSEEN`, and whether `OR`/`NOT` compose), after which the description is the same
shape of work the attachment fields just took.

## Trail

- 2026-08-11: opened by the sibling sweep that closed the per-field attachment schema
  descriptions, and it took that entry's place in the fix-when-it-bites bucket the same day, so
  the area count held at 4 rather than falling.
- 2026-08-11: the index states the trigger with a second arm the entry's own text does not carry,
  namely a deployment observed failing a search, offered beside the one live pass over the
  criteria worth naming.
