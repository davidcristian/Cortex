# A third thing a refused SELECT can mean, a name no mailbox could have, is untyped

**Status:** done 2026-08-22
**Area:** email-confirmer
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

Dovecot 2.3.21 answers a `SELECT` of the empty name with `[CANNOT] Invalid mailbox name: Name is
empty`, RFC 5530's code for a request the server will not even read as naming a mailbox. It is
neither of the two facts the classification is drawn between: nothing about it says the folder is
missing, and nothing says a folder is there and closed. The Bridge answers the same empty name with
the `no such mailbox` it gives every other wrong name, so the two servers disagree about which fact
this is, and only one of them has a word for it.

What happened was safe and silent: no measured phrase appears in the answer, so it stayed a plain
`MailboxError` saying the mailbox could not answer, which is true and unhelpful. The model guessed
a name that is not a name, and what it read back was indistinguishable from the Bridge being down.
Measured on the probe (`test_a_name_this_server_will_not_even_consider_is_a_third_answer` in
`test_imap_probe_live.py`).

Closing it needs a decision, since two readings are defensible. A name no mailbox could have is a
name no mailbox has, which argues for `FolderUnknownError` and the same one-call correction.
Against that, `[CANNOT]` is the server refusing the request rather than reporting the mailbox,
which is closer to what `SearchRefusedError` says about a query. Either way the signal is
machine-readable in a way neither missing-folder phrase is, so the change is a code test rather
than another phrase.

## History

- 2026-08-21: Filed by the close of [327](327-the-other-no-to-select-is-unseen.md), which ran a
  second IMAP server to settle what a refused SELECT means and met a third answer while it was
  there. Recorded in ADR-0057 decision 1.
- 2026-08-22: Done as `FolderUnknownError`, read off the response code (ADR-0056 decision 7). The
  decision went to the first reading: the port's error is the correction a caller can act on rather
  than a restatement of the server's claim, and the correction is identical whichever fact it was,
  so a third type would be a difference the port invented out of a difference in wording.
  `_FOLDER_MISSING_CODES` now holds `[cannot]` beside `[nonexistent]`, separate from the two
  measured phrases because they are different kinds of evidence, and the port contract gained a
  check that both calls taking a folder answer the empty name that way. Two things the measurement
  added: the probe sends `[CANNOT]` with six reasons rather than one, and five of them are forms a
  model really writes (`Parent/`, `/Parent`, `Parent//Child`, `INBOX/../etc`, `~root`); and a
  mutation showed the first version of the test could not tell the bracketed code from the English
  word inside it, which a refusal about a mailbox that is merely closed could easily contain, so a
  near-miss test now checks the brackets. One remainder opened, the folder name appearing inside
  the text the rule reads ([386](386-the-answer-read-holds-the-name-that-was-sent.md)).
