# A search of a folder holding one unreadable message is refused whole

**Status:** open, fix when it bites
**Area:** email
**Trigger:** a real account holds a message its server cannot open, and every `search_emails`
of that folder reads back `the mailbox could not run that search` rather than the messages the
server did deliver.
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-09-05 by the close of
[551](551-a-read-the-server-refuses-is-measured-by-hand-and-driven-by-no-live-row.md), whose
live row asserts that a search of the probe's `Sealed` is refused as `MailboxError`, the same
way the read is.

`ImapMailbox.search` in `brain/packages/email/src/cortex_email/imap.py` runs imap-tools'
`fetch`, which sends one `UID FETCH` for every uid the search matched and raises
`MailboxFetchError` when the tagged answer is not `OK`. Under `imap_fetch_failure = no-after`
Dovecot continues the FETCH past a message it cannot open and answers the tagged `NO` after
delivering the rest, so a folder holding one such message among readable ones answers every
search with the readable messages followed by a `NO`, and imap-tools drops the messages and
raises on the status. Under Dovecot's default the connection is dropped instead, so nothing is
delivered at all. The probe's `Sealed` holds one message and nothing else, so the row measures
the refusal and not the loss; the loss is read off imap-tools' `check_command_status` rather
than measured.

**Why it was left.** No account this repo reads has such a message, and the answer a model gets
is the fail-safe one: a mailbox that could not answer, which costs a dispatch and never a wrong
message. Reading the messages that did arrive off a `NO` would be the adapter deciding that a
partial answer is an answer, which is the reading the declined-read check exists to forbid for
the single message and would need its own argument for the list.

**What would close it.** A search in `ImapMailbox` that fetches headers one uid at a time and
skips a uid the server declines, reporting the skip, or that reads the delivered items off the
`NO` and marks the answer partial; either needs a contract check over a fixture holding one
unreadable message beside readable ones, which the probe could build by saving a second message
into `Sealed` before sealing the first.

## Trail

- 2026-09-05: opened by the close of
  [551](551-a-read-the-server-refuses-is-measured-by-hand-and-driven-by-no-live-row.md), which
  measured the refusal on a folder holding the sealed message alone.
