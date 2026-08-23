# The keep in the listing the adapter really makes is still proved on one account

**Status:** open, fix when it bites
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Trigger:** a second server this repo can reach starts flagging a name in a plain LIST and opening
it, or the Bridge account whose two flagged parents are the current proof stops being reachable

Opened 2026-08-23 by the close of
[376](376-the-bridge-flag-reading-is-one-account.md), which asked whether the probe could grow a
name Dovecot lists unselectable and still opens, and got two answers.

`list_folders` reads the flags off one call, imap-tools' plain `LIST "" "*"`, and keeps a flagged
name that opens. The close above put the premise under that rule on a fixture: dovecot 2.3.21
answers an `LSUB` of `%` with `(\Noselect) "/" Feigned` and then opens `Feigned`, which RFC 3501
section 6.3.9 obliges it to do. But `LSUB` is not the call the adapter makes, and in the call it
does make this server never produces the combination: there the flag and the refusal are computed
from one fact. Two configurations were built to move it and both failed, and their outputs are in
the ADR-0022 flagged-name-that-opens addendum.

So the keep branch of `_flagged_unselectable` and `_opens` in
`brain/packages/email/src/cortex_email/imap.py` is still exercised live by exactly one thing, the
Bridge test in `brain/packages/email/tests/test_email_live.py`, over one person's folder tree,
where `Folders` and `Labels` are flagged and open. The unit suite covers the branch over the
stand-in with the Bridge's flags recorded as `OPEN_NODE_FLAGS`, which keeps the shape honest and
proves nothing about a server.

**What would close it.** A server this repo can run that flags a name in a plain LIST and opens it.
Dovecot 2.3.21 is not it, and the next thing to try is not another Dovecot setting: it is another
server. Courier and Cyrus compute LIST attributes differently and one of them may list a namespace
root that selects; failing that, a small scripted IMAP responder in the probe stack, saying exactly
the two lines this needs, would pin the adapter's own branch at the cost of no longer being a real
server, which is the trade the two-server addendum spent a fixture avoiding. Weigh that honestly
before building one: a stub that says what it was told says nothing the stand-in does not.

## Trail

- 2026-08-23: opened by the close of
  [376](376-the-bridge-flag-reading-is-one-account.md), which landed the fixture that proves a real
  server can flag a name it opens, and left this, the same thing in the listing the adapter reads.
