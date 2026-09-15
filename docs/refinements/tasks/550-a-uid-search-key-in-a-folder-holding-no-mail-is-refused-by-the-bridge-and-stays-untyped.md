# A UID search key in a folder holding no mail is refused by the Bridge and stays untyped

**Status:** landed 2026-09-15
**Area:** email
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-09-05 by the close of
[548](548-an-empty-folder-read-raises-instead-of-answering-not-found.md), which moved the read
by uid off the search a ProtonMail Bridge refuses and left the search itself as it was.

Measured on 2026-09-05 against Proton Mail Bridge 03.26.00 at the protocol level:
`UID SEARCH CHARSET US-ASCII UID 999` in a folder whose message count is zero answers
`NO no such message` for every uid, and `OK` with nothing found in a folder holding mail;
Dovecot 2.3.21 answers `OK` with nothing found in both. Through the port,
`ImapMailbox.search("INBOX", "UID 999", 1)` on that Bridge raises `MailboxError: the mailbox
could not run that search: Response status "OK" expected, but "NO" received. Data: [b'no such
message']`, because `_search_failure` in `brain/packages/email/src/cortex_email/imap.py`
classifies only what imaplib raises, a `BAD` as `SearchRefusedError` and a dropped connection as
the base error, and a `NO` reaches `_translated` as imap-tools' `MailboxUidsError`.

**Why it was left.** `SEARCH_QUERY_HELP` does not name `UID` among the criteria, so a model has
not been told to write one, and every criterion the description does name was run against an
empty `INBOX` on the same day and accepted. The answer the model reads is the fail-safe one, a
mailbox that could not answer, which costs a dispatch and never a message.

**What would close it.** Either a classification in `search` that reads this `NO` as no matches,
which needs the care the read by uid took, since a `NO` to a search also covers a server that
declined for a reason of its own and the only evidence here is one server's words for a command
whose answer the standard does not define; or the message count read off the EXAMINE (`OK
[b'0']`) short-circuiting the search, which proves absence from the server's own count and asks
nothing. The second is the honest one and costs no round trip. It was not taken with the close
above because that close is about the read, and a search that returns nothing when a folder
holds nothing is a change to the other call.

## Trail

- 2026-09-05: opened by the close of
  [548](548-an-empty-folder-read-raises-instead-of-answering-not-found.md), which measured the
  refusal at the protocol level and routed the read by uid around it without touching the search.
- 2026-09-09: claims held against the code and the refusal read again live, and the trigger has
  not fired. `SEARCH_QUERY_HELP` in `brain/packages/email/src/cortex_email/values.py` still names
  no `UID` criterion, and `search` still classifies only what imaplib raises, so imap-tools'
  `MailboxUidsError` still reaches `_translated`. On the Bridge today, five of its nineteen folders
  hold no mail, and `UID SEARCH CHARSET US-ASCII UID 999` in two of them answers
  `('NO', [b'no such message'])` where the same key in a folder holding mail answers `OK` with the
  uid; through the port, `ImapMailbox.search("INBOX", "UID 999", 1)` raises the base `MailboxError`
  with that answer's words, unchanged from the record above. The EXAMINE the same reading takes
  answers the message count this entry proposes short-circuiting on.
- 2026-09-13: claims held against the code and the classification traced through the library
  itself, and nothing has moved. `SEARCH_QUERY_HELP` still names no `UID` criterion,
  `_search_failure` still reads only the exception type imaplib raises, and in imap-tools 1.13.0
  `BaseMailBox.fetch` runs the SEARCH through `uids`, whose `check_command_status(uid_result,
  MailboxUidsError)` raises on the `NO`. That error is an `ImapToolsError` rather than an
  `IMAP4.error`, so it passes the `except IMAP4.error` in `search` untouched and is wrapped by
  `_translated` as the base `MailboxError`, exactly as the body above records. The Bridge was not
  read again this sitting, so the live reading of 2026-09-09 stands.
- 2026-09-15: landed, and the closing move is the entry's second option narrowed. `search` reads
  the message count off the EXAMINE it already sends and answers a refused search with nothing
  found when that count is zero, so a folder holding no message matches no criteria whatever the
  server's reason for refusing was, and nothing of the `NO` is read. The blanket version this
  entry proposed, answering such a folder without sending any search, was written first and
  rejected on a measurement: with it in place the live row that sends every criterion
  `SEARCH_QUERY_HELP` names to the Bridge went red, because the account's `INBOX` holds no mail
  today and the row asked the server nothing. The Bridge was measured beside that: it accepts
  every advertised criterion in a folder holding no mail, answers the client syntax there with
  `BAD [Error offset=38]`, and refuses only the `UID` key, `NO no such message`, which is now
  answered from the count. The port contract gained
  `a_search_of_a_folder_holding_no_mail_matches_nothing`, driven over the fake, the stand-in and
  both servers, and the live Bridge row asserts both premises raw. The folder classification moved
  to `brain/packages/email/src/cortex_email/folders.py` to keep the adapter under the file cap.
  Opened [673](673-the-search-paths-dropped-connection-is-driven-by-no-live-row.md) from the same
  sitting, through the reading of
  [569](569-the-dropped-read-under-dovecots-default-is-measured-by-hand-and-driven-by-no-live-row.md).
