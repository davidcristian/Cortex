# A third thing a refused SELECT can mean, a name no mailbox could have, is untyped

**Status:** open, actionable
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-21 by the close of [327](327-the-other-no-to-select-is-unseen.md), which set out to
measure the two facts a `NO` to `SELECT` covers and found a third. Dovecot 2.3.21 answers a
`SELECT` of the empty name with `[CANNOT] Invalid mailbox name: Name is empty`, RFC 5530's code
for a request the server will not even read as naming a mailbox. It is neither of the two the
classification is drawn between: nothing about it says the folder is missing, and nothing says a
folder is there and shut. The Bridge answers the same empty name with the `no such mailbox` it
gives every other wrong name, so the two servers disagree about which fact this is, and only one
of them has a word for it.

What happens today is safe and silent: no measured phrase appears in the answer, so it stays a
plain `MailboxError` saying the mailbox could not answer, which is true and unhelpful. The model
guessed a name that is not a name, and what it reads back is indistinguishable from the Bridge
being down. Measured and pinned on the probe
(`test_a_name_this_server_will_not_even_consider_is_a_third_answer` in `test_imap_probe_live.py`),
so the fact is on record rather than latent.

**What would close it.** A decision first, since two readings are defensible and neither is
obvious. A name no mailbox could have is a name no mailbox has, which argues for
`FolderUnknownError` and the same one-call correction: `list_folders` really is where the answer
is. Against that, `[CANNOT]` is the server refusing the request rather than reporting the mailbox,
which is closer to what `SearchRefusedError` says about a query, and typing it as missing would
have the port assert something the server declined to assert. Whichever wins, the signal is
machine-readable in a way neither missing-folder phrase is, so the change is a code test rather
than another phrase, and it wants the same treatment the two measured phrases got: read from a
server, not from the RFC alone. The probe produces one on demand, and the Bridge's disagreement is
already measured, so both sides of the decision can be checked before anything is written.

## Trail

- 2026-08-21: Filed by the close of [327](327-the-other-no-to-select-is-unseen.md), which ran a
  second IMAP server to settle what a refused SELECT means and met a third answer while it was
  there. Recorded in the ADR-0022 two-server addendum.
