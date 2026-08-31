# One of the two unselectable flags is read from a standard and from no server

**Status:** landed 2026-08-22
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-08-21 by the close of [364](364-list-folders-offers-a-name-no-mailbox-has.md), which
made `list_folders` drop the names a server flags unselectable. `_NOT_A_MAILBOX` in
`brain/packages/email/src/cortex_email/imap.py` holds two spellings, and only one of them was
measured. `\Noselect` is what the probe's Dovecot 2.3.21 really sends, recorded verbatim in the
ADR-0022 hierarchy-node addendum. `\NonExistent` is RFC 5258's spelling of the same fact for a
server that speaks LIST-EXTENDED, and no server this repo has connected to has ever sent it: the
unit test that pins it (`test_the_newer_spelling_of_unselectable_is_dropped_too`) drives it through
a stand-in that was told to say it.

So half the filter rests on a reading of a standard rather than on an answer somebody saw. That is
the weaker of the two kinds of evidence this area has been holding itself to, where the missing
folder phrases are each a sentence a real server sent, and the risk is not that the spelling is
wrong but that the shape around it is: whether such a server sends it instead of `\Noselect` or
beside it, and whether the name it comes with behaves the way the measured one does.

**What would close it.** Either a measurement or a downgrade of the claim. Dovecot answers
LIST-EXTENDED when the client asks for it, and imap-tools' `folder.list()` does not, so the cheap
version is a direct imaplib dialogue against the running probe (`just up-imap-probe`) issuing an
extended LIST and recording what the `Parent` node comes back flagged as. If it can be produced, the
wording joins the addendum beside the one already there and the unit test can be driven from the
recorded answer rather than an invented one. If it cannot, the right close is to say in the comment
that the second spelling is defensive and unmeasured, which is what the neighbouring measured
phrases already say about themselves.

That dialogue was run and the sentence above is wrong about where it would lead: `Parent` comes back
`\Noselect` under every extended LIST this server accepts, because dovecot converts its own
nonexistent flag *down* to `\Noselect` for a client that did not ask and never up, and a node with
a child on disk is not nonexistent in its model. The word turned out to belong to another fact
entirely, which is what the close measured instead.

## Trail

- 2026-08-22: Landed as a measurement rather than a downgrade (ADR-0022 newer-spelling addendum).
  `\NonExistent` is a word this server really sends, but for a subscribed name no mailbox has and
  only to a listing that asks for subscriptions: `(\Subscribed \NonExistent) "/" Ghost`, arriving
  instead of `\Noselect` rather than beside it, on a name a SELECT then refuses in the very words
  the node is refused in. So both halves of the shape question are answered. The probe grew a
  fifth name to produce it, written into the account's subscription file because this server
  refuses a SUBSCRIBE of a name no mailbox has, and it is a registered coupling like the other
  four. The spelling stays in `_NOT_A_MAILBOX` and the comment now says what kind of evidence it
  is: the plain `LIST "" "*"` that `folder.list()` sends cannot carry the word on a conformant
  server, and the Bridge answers an extended LIST with `BAD`, so reading it is a defence against a
  server not yet met rather than a live path.
- 2026-08-21: Filed by the close of [364](364-list-folders-offers-a-name-no-mailbox-has.md), which
  added the flag beside the one it measured. Recorded in the ADR-0022 hierarchy-node addendum.
