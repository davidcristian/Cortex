# A UID search key in a folder holding no mail is refused by the Bridge and stays untyped

**Status:** open, fix when it bites
**Area:** email
**Trigger:** a model writes a `UID` criterion into `search_emails` against a folder holding no
mail and reads back `the mailbox could not run that search` rather than
`(no matching messages)`, which taints the turn.
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
