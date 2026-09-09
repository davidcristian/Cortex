# The keep in the listing the adapter really makes is still proved on one account

**Status:** open, fix when it bites
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-09-09
**Trigger:** a second server this repo can reach starts flagging a name in a plain LIST and opening
it, or the Bridge account whose two flagged parents are the current proof stops being reachable.
Both limbs come off one reading, a plain `LIST "" "*"` taken past the port with every listed name
opened: on the probe after `just up-imap-probe`, and on the Bridge through `ImapMailbox`. This
entry's trail records the counts and the flags each server answered with when that was last run.

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
server, which is the trade the two-server addendum spent a fixture avoiding. Weigh that
before building one: a stub answering with the two lines it was given proves no more than the
stand-in already does.

## Trail

- 2026-08-23: opened by the close of
  [376](376-the-bridge-flag-reading-is-one-account.md), which landed the fixture that proves a real
  server can flag a name it opens, and left this, the same thing in the listing the adapter reads.
- 2026-09-07: trigger swept and not fired, on both limbs. The Bridge account is still reachable
  and is still the proof: read live today, it lists 19 names, flags `Folders` and `Labels`
  `(\Noselect, \Unmarked)`, opens both, and opens all 19, so what `list_folders` offers and what
  the server opens are the same set. No second server has started flagging a name in a plain LIST
  and opening it either. The probe still answers a plain LIST with `Feigned` as `(\HasChildren)`
  and nothing else, which `brain/packages/email/tests/test_imap_probe_live.py` asserts by name,
  and the image it says that against has not moved. Recorded in the ADR-0022 trigger-sweep
  addendum.
- 2026-09-08: read again on both limbs, neither fired, and the line above is corrected. The Bridge
  account is reachable and is still the proof: read live, it lists 19 names, offers 19, opens 19,
  and flags `Folders` and `Labels` `('\Noselect', '\Unmarked')`, both of which open, so the keep
  branch is taken twice on this account and nowhere else live. The probe was started and its plain
  LIST read past the port: seven names, one of them flagged, `Parent (\Noselect \HasChildren)`,
  which does not open, so this server still produces the drop branch and not the keep. The
  correction is what the probe says about `Feigned`. Its plain LIST answered
  `(\HasChildren \UnMarked)`, not `(\HasChildren)` alone, and the suite does not assert that tuple:
  `test_a_name_this_server_calls_unselectable_and_opens_anyway_is_a_real_thing` asserts that
  `\HasChildren` is present and that neither unselectable word is, deliberately, because this server
  starts sending `\UnMarked` once something has searched the name and the contract check searches
  every offered name. The suite's own comment records an exact reading being written, passing on the
  container that built it, and failing on the rerun. Recorded in the ADR-0022 addendum of the same
  day.
- 2026-09-09: claims held against the code and both limbs read again, neither fired. The Bridge
  account is reachable and is still the only live proof: read live today it lists 19 names, offers
  19, opens 19, and flags `Folders` and `Labels` `('\Noselect', '\Unmarked')`, both of which open,
  so the keep branch is taken twice there and nowhere else live. No second server has started
  flagging a name in a plain LIST and opening it, the one IMAP server image any compose file names
  being unmoved at the digest recorded for it. The stand-in's `OPEN_NODE_FLAGS` is still the
  Bridge's own pair, in `brain/packages/email/tests/imap_stub.py`.
