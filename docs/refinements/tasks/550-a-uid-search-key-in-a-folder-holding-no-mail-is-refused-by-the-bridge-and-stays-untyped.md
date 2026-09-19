# A UID search key in a folder with no mail is refused by the Bridge and stays untyped

**Status:** done 2026-09-15
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

Measured on 2026-09-05 against Proton Mail Bridge 03.26.00 at the protocol level:
`UID SEARCH CHARSET US-ASCII UID 999` in a folder whose message count is zero answers
`NO no such message` for every uid, and `OK` with nothing found in a folder with mail; Dovecot
2.3.21 answers `OK` with nothing found in both. Through the port,
`ImapMailbox.search("INBOX", "UID 999", 1)` on that Bridge raises
`MailboxError: the mailbox could not run that search: Response status "OK" expected, but "NO" received. Data: [b'no such message']`,
because `_search_failure` in `brain/packages/email/src/cortex_email/imap.py` classifies only what
imaplib raises, a `BAD` as `SearchRefusedError` and a dropped connection as the base error, while a
`NO` reaches `_translated` as imap-tools' `MailboxUidsError`.

`SEARCH_QUERY_HELP` does not name `UID` among the criteria, so a model has not been told to write
one, and every criterion the description does name was run against an empty `INBOX` on the same day
and accepted. The answer the model reads is the fail-safe one, a mailbox that could not answer,
which costs a dispatch and never a message.

Two ways to close it: classify this `NO` in `search` as no matches, which needs the care the read by
uid took, since a `NO` to a search also covers a server that declined for a reason of its own; or
read the message count off the EXAMINE (`OK [b'0']`) and skip the search, which proves absence from
the server's own count and asks nothing.

## History

- 2026-09-05: opened by the close of
  [548](548-an-empty-folder-read-raises-instead-of-answering-not-found.md), which measured the
  refusal at the protocol level and routed the read by uid around it without touching the search.
- 2026-09-09: claims checked against the code and the refusal read again live, and the trigger has
  not fired. `SEARCH_QUERY_HELP` in `brain/packages/email/src/cortex_email/values.py` still names no
  `UID` criterion, and `search` still classifies only what imaplib raises. On the Bridge today, five
  of its nineteen folders have no mail, and `UID SEARCH CHARSET US-ASCII UID 999` in two of them
  answers `('NO', [b'no such message'])` where the same key in a folder with mail answers `OK` with
  the uid. The EXAMINE answers the message count this entry proposes reading.
- 2026-09-13: claims checked and the classification traced through the library, and nothing has
  moved. In imap-tools 1.13.0 `BaseMailBox.fetch` runs the SEARCH through `uids`, whose
  `check_command_status(uid_result, MailboxUidsError)` raises on the `NO`. That error is an
  `ImapToolsError` rather than an `IMAP4.error`, so it passes the `except IMAP4.error` in `search`
  untouched and is wrapped by `_translated` as the base `MailboxError`. The Bridge was not read
  again, so the live reading of 2026-09-09 stands.
- 2026-09-15: done, by the second option narrowed. `search` reads the message count off the EXAMINE
  it already sends and answers a refused search with nothing found when that count is zero, so a
  folder with no message matches no criteria whatever the server's reason for refusing was, and
  nothing of the `NO` is read. The blanket version this entry proposed, answering such a folder
  without sending any search, was written first and rejected on a measurement: with it in place the
  live row that sends every criterion `SEARCH_QUERY_HELP` names went red, because the account's
  `INBOX` has no mail today and the row asked the server nothing. The Bridge was measured beside
  that: it accepts every advertised criterion in a folder with no mail, answers the client syntax
  there with `BAD [Error offset=38]`, and refuses only the `UID` key. The port contract gained
  `a_search_of_a_folder_holding_no_mail_matches_nothing`, driven over the fake, the stand-in and
  both servers, and the live Bridge row asserts both premises raw. The folder classification moved
  to `brain/packages/email/src/cortex_email/folders.py` to keep the adapter under the file cap.
  Opened [673](673-the-search-paths-dropped-connection-is-driven-by-no-live-row.md) from the same
  session, through the reading of
  [569](569-the-dropped-read-under-dovecots-default-is-measured-by-hand-and-driven-by-no-live-row.md).
