# A read of an empty folder raises instead of answering not-found, so the turn is tainted

**Status:** done 2026-09-05
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

`Mailbox.fetch` is documented to return `None` when the message does not exist
(`brain/packages/email/src/cortex_email/imap.py`), and `read_email` builds
`message <uid> not found in <folder>` from that `None`, which the brain marks `Trust.TRUSTED` under
the own-text rule. Against a real ProtonMail Bridge that holds in a folder with mail and fails in
one with none: every uid there is answered `NO ... no such message`, `_translated` classifies it as
a plain `MailboxError`, FastMCP restates it as `Error executing tool read_email: ...`, and the
overlay has no matching text. So a `read_email` of an empty folder taints the turn and closes its
outbound tools over a message that was never read, the exact cost the own-text overlay was built to
remove.

Measured on 2026-09-04 against a live Bridge, one call per folder: `All Mail`, `Sent` and
`Folders/Spammy` answer a uid no message has with `None`; `INBOX`, `Archive` and `Starred`, each
holding no mail, raise for every uid tried, `4294967290` and `999` alike. The cause is the folder's
emptiness rather than the uid. The in-process tests cannot see this, since `mailbox_fake.py` returns
`None` for any uid in any folder and `mailbox_contract.py` has no case for a uid that is not there.

## History

- 2026-09-04: opened by the live half of
  [533](533-the-unfenced-correction-is-unmeasured-on-the-cortex.md), which measured it against a
  real Bridge ([untrusted-framing](../../readings/untrusted-framing.md)).
- 2026-09-05: done. Checked at the protocol level against Proton Mail Bridge 03.26.00: the
  `NO no such message` answers the `UID SEARCH` imap-tools sends before its FETCH rather than the
  FETCH, and only in a folder whose message count is zero; the `UID FETCH` itself answers `OK` with
  no data in every folder, which RFC 3501 defines as a uid no message has, on the Bridge and on the
  probe's Dovecot 2.3.21 alike. `ImapMailbox.fetch` now sends that one FETCH
  (`brain/packages/email/src/cortex_email/uidfetch.py`), reads absence off its answer, checks the
  uid against RFC 3501's grammar first, and raises for any other status. Two faults the entry did
  not name went with it: imap-tools' own `TypeError` for `abc` had been crossing the port as itself,
  and `1:*` had returned the folder's first message under a uid nobody named. The contract gained
  four cases over both fixtures, the live row moved into the trusted set and passes against the
  Bridge, and the email and probe suites gained a row each. The rule is
  [ADR-0056](../../adr/ADR-0056-email-reader-answers.md) decisions 10 and 11. Opens
  [550](550-a-uid-search-key-in-a-folder-holding-no-mail-is-refused-by-the-bridge-and-stays-untyped.md),
  [551](551-a-read-the-server-refuses-is-measured-by-hand-and-driven-by-no-live-row.md) and
  [552](552-the-uid-parameter-of-read-email-carries-no-description.md).
