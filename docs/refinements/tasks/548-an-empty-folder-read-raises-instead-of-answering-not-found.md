# A read of an empty folder raises instead of answering not-found, so the turn is tainted

**Status:** landed 2026-09-05
**Area:** email
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-09-04 by the live half of
[533](533-the-unfenced-correction-is-unmeasured-on-the-cortex.md), which drove the own-text
overlay against a real ProtonMail Bridge and found one of the five declared answers unreachable
there.

`Mailbox.fetch` promises `None` when the message does not exist
(`brain/packages/email/src/cortex_email/imap.py`), and `read_email` composes
`message <uid> not found in <folder>` from that `None`, which the brain re-stamps
`Trust.TRUSTED` under the own-text rule. Against this Bridge the promise holds in a folder that
holds mail and fails in one that holds none: every uid there is answered
`NO ... no such message`, `_translated` classifies it as a plain `MailboxError`, FastMCP restates
it as `Error executing tool read_email: ...`, and the overlay has no matching text. So a
`read_email` of an empty folder taints the turn and closes its outbound surface, over a message
that was never read, which is the exact cost the own-text overlay was built to remove.

Measured on 2026-09-04 against a live Bridge, one call per folder: `All Mail`, `Sent` and
`Folders/Spammy` answer a uid no message has with `None`; `INBOX`, `Archive` and `Starred`, each
holding no mail, raise for every uid tried, the plausible-looking `4294967290` and the
plausible `999` alike. The fault is the folder's emptiness rather than the uid.

The in-process checks cannot see this. `mailbox_fake.py` returns `None` for any uid in any
folder, and `mailbox_contract.py` has no check for a uid that is not there at all, so nothing
holds either implementation to the sentence the port's own docstring makes.

**What would close it.** A contract check that a uid no message has returns `None`, run over the
fake and over the real adapter alike, plus the classification in `ImapMailbox.fetch` that makes
the real one pass: an empty folder's `NO` to a fetch is a message that is not there, not a
mailbox that could not answer. The care ADR-0022's unknown-folder addendum took applies here in
the same shape, since a `NO` to a fetch can also mean the server declined for a reason of its
own, and a message that cannot be proved absent must not be reported absent. The live row that
records today's behaviour is
`test_a_read_of_an_empty_folder_never_reaches_the_not_found_answer` in
`brain/packages/orchestrator/tests/test_own_texts_bridge_live.py`, and it goes red on the fix,
which is where the case moves up into the trusted set beside the other four.

## Trail

- 2026-09-04: opened by the live half of
  [533](533-the-unfenced-correction-is-unmeasured-on-the-cortex.md), which measured it against a
  real Bridge and recorded it in the ADR-0013 addendum on the own texts against a Bridge.
- 2026-09-05: landed. Re-derived at the protocol level against Proton Mail Bridge 03.26.00, the
  `NO no such message` answers the `UID SEARCH` imap-tools sends before its FETCH rather than a
  FETCH, and only in a folder whose message count is zero; the `UID FETCH` itself answers `OK`
  with no data in every folder, which RFC 3501 defines as a uid no message has, on the Bridge and
  on the probe's Dovecot 2.3.21 alike. `ImapMailbox.fetch` now sends that one FETCH
  (`brain/packages/email/src/cortex_email/uidfetch.py`), reads absence off its answer, holds the
  uid to RFC 3501's grammar first, and raises for any other status. Two faults the entry did not
  name went with it: imap-tools' own `TypeError` for `abc` had been crossing the port as itself,
  and `1:*` had returned the folder's first message under a uid nobody named. The contract gained
  four checks over both fixtures, the live row moved into the trusted set and passes off the
  Bridge, and the email and probe suites gained a row each. Written up in the
  [ADR-0022 addendum on reading absence off the FETCH's own answer](../../adr/ADR-0022-email-write-confirmer.md#addendum-2026-09-05-a-message-that-is-not-there-is-read-off-the-fetchs-own-answer),
  with the mutation table. Opens
  [550](550-a-uid-search-key-in-a-folder-holding-no-mail-is-refused-by-the-bridge-and-stays-untyped.md),
  [551](551-a-read-the-server-refuses-is-measured-by-hand-and-driven-by-no-live-row.md) and
  [552](552-the-uid-parameter-of-read-email-carries-no-description.md).
