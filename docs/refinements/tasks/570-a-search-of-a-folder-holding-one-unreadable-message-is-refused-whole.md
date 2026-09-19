# A search of a folder holding one unreadable message is refused whole

**Status:** open, waiting for its trigger
**Area:** email
**Trigger:** a real account holds a message its server cannot open, and a `search_emails` of that
folder whose first `limit` matches include it reads back `the mailbox could not run that search`
rather than the messages the server did deliver. Read it past the port by searching every folder
`list_folders` offers for `ALL` with a limit no smaller than that folder's message count. The live
test `test_a_folder_no_mailbox_has_is_refused_by_name_and_by_the_folder_list` searches each folder
at a limit of 1, so it fetches only the first message each search returns.
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)
**Verified:** 2026-09-19

`ImapMailbox.search` in `brain/packages/email/src/cortex_email/imap.py` runs imap-tools' `fetch`,
which at its default `bulk=False` sends one `UID FETCH` per uid through `_fetch_by_one` and raises
`MailboxFetchError` as soon as one of those commands answers anything but `OK`. So the message the
server declines is refused by a command of its own, and the readable messages beside it are fetched
by commands that answer `OK`. What loses those is this side of the connection: `search` builds
`list(box.fetch(...))`, and that generator has already produced the readable messages it reached
before the declined uid raises, so the exception discards them.

Two limits follow, both measured on 2026-09-15 by saving two readable messages into the probe's
`Sealed` beside the sealed one and moving the seal between them. The search is refused whole only
when the declined uid is among the first `limit` matches, since imap-tools cuts the uid list to the
limit before it sends any FETCH: with the sealed message at uid 3, `limit=1` and `limit=2` answered
normally and `limit=3` and `limit=5` were refused. And which messages are lost follows uid order
rather than what the server delivered: with the sealed message at uid 3 the generator produced uids
1 and 2 before raising, and with it at uid 1 it produced nothing. Under Dovecot's default the
connection is dropped instead, which ends the rest of the run as well.

No account this repo reads has such a message, and the answer a model gets is the fail-safe one, a
mailbox that could not answer, which costs a dispatch and never a wrong message. Closing it means a
search in `ImapMailbox` that sends the header fetches itself, as `uidfetch.py` already does for the
read by uid, and skips a uid the server declines while reporting the skip. Reading the delivered
items off the `NO` is not an option, since imap-tools checks the command status before it looks at
the data and one uid per command leaves nothing to recover. The skip needs a contract case over a
fixture holding one unreadable message beside readable ones.

## History

- 2026-09-05: opened by the close of
  [551](551-a-read-the-server-refuses-is-measured-by-hand-and-driven-by-no-live-row.md), which
  measured the refusal on a folder holding the sealed message alone.
- 2026-09-09: claims checked, and the mechanism was wrong. imap-tools 1.13.0 fetches one uid per
  command at the default `bulk=False` this adapter uses, so this was never one FETCH delivering the
  readable messages ahead of a `NO`; those messages are fetched successfully and then discarded by
  the `list` in `search`. The trigger has not fired: read live today, the Bridge account lists
  nineteen folders and every one answers a search.
- 2026-09-13: the mechanism was read out of imap-tools 1.13.0's own source rather than its
  documentation, and every claim held. The probe's `Sealed` still holds the one message
  `docker/dovecot/probe-mailboxes.sh` saves into it. The Bridge was not read again, so the live
  reading of 2026-09-09 stands.
- 2026-09-15: the loss was measured rather than inferred, and every claim held. Two readable
  messages were saved into the probe's `Sealed` through `doveadm` in the running container and the
  seal moved between them, which is the fixture the fix needs and which no committed file builds.
  The trigger has not fired: the Bridge account lists nineteen folders and every one answers a
  search. The fix is unchanged and still large, so this stays open.
- 2026-09-19: the code claims held and the trigger was repaired. `search` still builds
  `list(box.fetch(...))`, and the empty-folder change of 2026-09-15 catches only `MailboxUidsError`,
  which a declined FETCH does not raise, so a sealed message in a folder with mail is still refused
  whole; imap-tools is still 1.13.0 in `brain/uv.lock`, and the probe's `Sealed` still holds one
  message. The trigger said every search of the folder is refused, which the limit reading above
  contradicts, so it now says which searches are refused and how to read it: the two live readings
  do not record the limit they searched at, and at the live test's limit of 1 a folder answering
  shows only that its first message opens. The Bridge was not read that night.
