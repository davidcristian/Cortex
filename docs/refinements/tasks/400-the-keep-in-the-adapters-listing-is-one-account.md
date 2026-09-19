# The keep branch in the listing the adapter really makes is proved on one account

**Status:** open, waiting for its trigger
**Area:** email-confirmer
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)
**Verified:** 2026-09-19
**Trigger:** a second server this repo can reach starts flagging a name in a plain LIST and opening
it, or the Bridge account whose two flagged parents are the current proof stops being reachable.
Both parts come off one reading, a plain `LIST "" "*"` taken through the port with every listed
name opened: on the probe after `just up-imap-probe`, and on the Bridge through `ImapMailbox`. The
probe part can change only when its image line in `docker/docker-compose.imap-probe.yml` or the
mailboxes `docker/dovecot/probe-mailboxes.sh` builds change; the Bridge part needs a live run
against the account. The history below records the counts and the flags each server answered with
when that was last run.

`list_folders` reads the flags off one call, imap-tools' plain `LIST "" "*"`, and keeps a flagged
name that opens. [376](376-the-bridge-flag-reading-is-one-account.md) put the premise under that
rule on a fixture: dovecot 2.3.21 answers an `LSUB` of `%` with `(\Noselect) "/" Feigned` and then
opens `Feigned`, which RFC 3501 section 6.3.9 requires. But `LSUB` is not the call the adapter
makes, and in the call it does make this server never produces the combination: there the flag and
the refusal are computed from one fact. Two configurations were built to change that and both
failed, and their outputs are in
[docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md).

So the keep branch of `flagged_unselectable` and `kept_after_opening` in
`brain/packages/email/src/cortex_email/folders.py` is exercised live by exactly one thing, the
Bridge test in `brain/packages/email/tests/test_email_live.py` that compares every name the server
opens with the set `list_folders` offers, over one person's folder tree, where `Folders` and
`Labels` are flagged and open. The test names neither; the flags are the account's. The unit suite
covers the branch over the stand-in with the Bridge's flags recorded as `OPEN_NODE_FLAGS`, which
keeps the shape right and proves nothing about a server.

**What would close it.** A server this repo can run that flags a name in a plain LIST and opens it.
Dovecot 2.3.21 is not it, and the next thing to try is another server rather than another Dovecot
setting. Courier and Cyrus compute LIST attributes differently and one of them may list a namespace
root that selects. Failing that, a small scripted IMAP responder in the probe stack, saying exactly
the two lines this needs, would exercise the adapter's branch at the cost of no longer being a real
server, which is the trade [ADR-0057](../../adr/ADR-0057-imap-probe-server.md) spent a fixture
avoiding: a stub answering with the two lines it was given proves no more than the stand-in does.

## History

- 2026-08-23: opened by the close of
  [376](376-the-bridge-flag-reading-is-one-account.md), which added the fixture proving a real
  server can flag a name it opens, and left this, the same thing in the listing the adapter reads.
- 2026-09-07: trigger checked and not fired, on both parts. The Bridge account is still reachable
  and is still the proof: read live, it lists 19 names, flags `Folders` and `Labels`
  `(\Noselect, \Unmarked)`, opens both, and opens all 19, so what `list_folders` offers and what
  the server opens are the same set. No second server has started flagging a name in a plain LIST
  and opening it. The probe still answers a plain LIST with `Feigned` as `(\HasChildren)` and
  nothing else, which `brain/packages/email/tests/test_imap_probe_live.py` checks by name.
- 2026-09-08: read again on both parts, neither fired, and the line above is corrected. The Bridge
  account is reachable and is still the proof: it lists 19 names, offers 19, opens 19, and flags
  `Folders` and `Labels` `('\Noselect', '\Unmarked')`, both of which open, so the keep branch is
  taken twice on this account and nowhere else live. The probe was started and its plain LIST read
  through the port: seven names, one flagged, `Parent (\Noselect \HasChildren)`, which does not
  open, so this server still produces the drop branch and not the keep. The correction is what the
  probe says about `Feigned`: its plain LIST answered `(\HasChildren \UnMarked)`, not
  `(\HasChildren)` alone, and the suite does not assert that tuple.
  `test_a_name_this_server_calls_unselectable_and_opens_anyway_is_a_real_thing` asserts that
  `\HasChildren` is present and that neither unselectable word is, deliberately, because this
  server starts sending `\UnMarked` once something has searched the name and the contract check
  searches every offered name. The suite's own comment records an exact reading being written,
  passing on the container that built it, and failing on the rerun.
- 2026-09-09: claims checked against the code and both parts read again, neither fired. The Bridge
  account is reachable and is still the only live proof: 19 names listed, 19 offered, 19 opened,
  with `Folders` and `Labels` flagged `('\Noselect', '\Unmarked')` and both opening. No second
  server has started flagging a name in a plain LIST and opening it, the one IMAP server image any
  compose file names being unmoved at the digest recorded for it. The stand-in's `OPEN_NODE_FLAGS`
  is still the Bridge's own pair, in `brain/packages/email/tests/imap_stub.py`.
- 2026-09-12: claims checked, and the probe part read again rather than quoted. The probe was
  started and its plain `LIST "" "*"` taken through the port: seven names, one flagged,
  `Parent (\Noselect \HasChildren)`, refused
  `Mailbox doesn't exist: Parent (0.001 + 0.000 secs).`, so this server still produces the drop
  branch and not the keep, and `just email-folder-probe` passed 9 of 9 against it. The Bridge part
  was not read, the slot having ruled out a live run, so the account's reachability is still the
  reading of 2026-09-09. The keep branch itself moved a little and is still the branch this entry
  is about: `_opens` is now `_kept_after_opening` and drops a flagged name only when the refusal
  proves no mailbox has it ([375](375-a-flagged-name-shut-is-dropped-as-if-missing.md)), which
  widens what is kept and leaves the thing with no fixture where it was, since dovecot 2.3.21 flags
  no name in this listing that it will open at all.
- 2026-09-17: claims checked, the probe part read again, neither part fired. The listing rule moved
  on 2026-09-15 from `imap.py` to `folders.py`, where `_flagged_unselectable` and
  `_kept_after_opening` are now the public `flagged_unselectable` and `kept_after_opening`,
  unchanged by an AST comparison of the two versions. No change to `docker/dovecot/` or the probe's
  compose file since 2026-09-12. The probe was started and its plain `LIST "" "*"` read through the
  port: seven names, one flagged, `Parent (\Noselect \HasChildren)`, refused
  `Mailbox doesn't exist: Parent (0.001 + 0.000 secs).`, and `list_folders` offered the other six,
  so this server still produces the drop branch and not the keep; `Feigned` was listed unflagged,
  `(\HasChildren \UnMarked)`. The probe's live suite passed 9 of 9. The Bridge part was not read,
  so the account's reachability is still the reading of 2026-09-09, now eight days old; the next
  review of this entry should read it live. The stand-in's `OPEN_NODE_FLAGS` is still the Bridge's
  own pair, at `brain/packages/email/tests/imap_stub.py:124`.
- 2026-09-19: claims checked against the code; the probe part is unchanged by its own rule, and the
  Bridge part was not read again. `flagged_unselectable` and `kept_after_opening` in `folders.py`
  have no commit since 2026-09-15, `OPEN_NODE_FLAGS` is still the Bridge's pair at
  `brain/packages/email/tests/imap_stub.py:124`, and the live row still reaches
  `_assert_no_name_this_server_opens_is_withheld`. Neither `docker/dovecot/` nor the probe's
  compose file has a commit since 2026-09-05, and the local `dovecot/dovecot:2.3.21` resolves to
  the digest recorded in
  [docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md), so the plain LIST
  read on 2026-09-17 still applies without restarting the probe. Tonight's run ruled out a live run
  against the account, so its reachability is still the reading of 2026-09-09, now ten days old,
  and the note of 2026-09-17 that the next review should read it live still applies.
