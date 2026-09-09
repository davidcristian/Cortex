# A search of a folder holding one unreadable message is refused whole

**Status:** open, fix when it bites
**Area:** email
**Trigger:** a real account holds a message its server cannot open, and every `search_emails`
of that folder reads back `the mailbox could not run that search` rather than the messages the
server did deliver.
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-09-09

Opened 2026-09-05 by the close of
[551](551-a-read-the-server-refuses-is-measured-by-hand-and-driven-by-no-live-row.md), whose
live row asserts that a search of the probe's `Sealed` is refused as `MailboxError`, the same
way the read is.

`ImapMailbox.search` in `brain/packages/email/src/cortex_email/imap.py` runs imap-tools'
`fetch`, which at its default `bulk=False` sends one `UID FETCH` per uid through `_fetch_by_one`
and raises `MailboxFetchError` as soon as one of those commands answers anything but `OK`. So the
message the server declines is refused by a command of its own, and the readable messages beside
it are fetched by commands that answer `OK`. What loses those is this side of the wire: `search`
builds `list(box.fetch(...))`, and that generator has already yielded the readable messages it
reached before the declined uid raises, so the exception discards them.

Two limits follow from the per-uid shape. The search is refused whole only when the declined uid
is among the first `limit` matches, since imap-tools cuts the uid list to the limit before it
sends any FETCH. And which messages are lost is a matter of uid order rather than of what the
server delivered: under `imap_fetch_failure = no-after` the tagged `NO` covers the one message,
and under Dovecot's default the connection is dropped, which ends the rest of the run as well.
The probe's `Sealed` holds one message and nothing else, so the live row measures the refusal and
not the loss; the loss is read off imap-tools' `_fetch_by_one` and the `list` in `search` rather
than measured.

**Why it was left.** No account this repo reads has such a message, and the answer a model gets
is the fail-safe one: a mailbox that could not answer, which costs a dispatch and never a wrong
message. Returning the messages that were fetched before the refusal would be the adapter
deciding that a partial answer is an answer, which is the reading the declined-read check exists to forbid for
the single message and would need its own argument for the list.

**What would close it.** A search in `ImapMailbox` that sends the header fetches itself, as
`uidfetch.py` already does for the read by uid, and skips a uid the server declines while
reporting the skip. Reading the delivered items off the `NO` is not a second option: imap-tools
checks the command status before it looks at the data, and one uid per command leaves nothing
beside the declined message for such a read to recover. The skip needs a contract check over a
fixture holding one unreadable message beside readable ones, which the probe could build by
saving a second message into `Sealed` before sealing the first.

## Trail

- 2026-09-05: opened by the close of
  [551](551-a-read-the-server-refuses-is-measured-by-hand-and-driven-by-no-live-row.md), which
  measured the refusal on a folder holding the sealed message alone.
- 2026-09-09: claims held against the code, and the mechanism was wrong. imap-tools 1.13.0
  fetches one uid per command at the default `bulk=False` this adapter uses, so this was never one
  FETCH delivering the readable messages ahead of a `NO`; those messages are fetched successfully
  and then discarded by the `list` in `search` when the declined uid raises. The outcome the title
  names is unchanged, and the body now carries the two limits the per-uid shape imposes and drops
  the partial-answer option, which has nothing to read. The trigger has not fired: read live
  today, the Bridge account lists nineteen folders and every one of them answers a search, none
  refused.
