# One of the two unselectable flags is read from a standard and from no server

**Status:** done 2026-08-22
**Area:** email-confirmer
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

`_NOT_A_MAILBOX` in `brain/packages/email/src/cortex_email/imap.py` holds two flag names, and only
one of them was measured. `\Noselect` is what the probe's Dovecot 2.3.21 really sends, recorded
word for word in [docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md).
`\NonExistent` is RFC 5258's name for the same fact on a server that speaks LIST-EXTENDED, and no
server this repo has connected to had ever sent it: the unit test that covers it
(`test_the_newer_form_of_unselectable_is_dropped_too`) drives it through a stand-in that was
told to say it.

So half the filter rested on a reading of a standard rather than on an answer somebody saw. The
risk is not that the name is wrong but that the shape around it is: whether such a server sends it
instead of `\Noselect` or beside it, and whether the name it comes with behaves the way the
measured one does.

Closing it needs either a measurement or a weaker claim. Dovecot answers LIST-EXTENDED when the
client asks for it and imap-tools' `folder.list()` does not, so the cheap version is a direct
imaplib dialogue against the running probe (`just up-imap-probe`) issuing an extended LIST.

## History

- 2026-08-21: Filed by the close of [364](364-list-folders-offers-a-name-no-mailbox-has.md), which
  added the flag beside the one it measured. Recorded in ADR-0056 decision 8.
- 2026-08-22: Done as a measurement rather than a weaker claim (ADR-0056 decision 9). The dialogue
  was run, and the guess above about where it would lead was wrong: `Parent` comes back `\Noselect`
  under every extended LIST this server accepts, because dovecot converts its own nonexistent flag
  down to `\Noselect` for a client that did not ask and never up, and a node with a child on disk
  is not nonexistent in its model. `\NonExistent` is a word this server really sends, but for a
  subscribed name no mailbox has and only to a listing that asks for subscriptions:
  `(\Subscribed \NonExistent) "/" Ghost`, arriving instead of `\Noselect` rather than beside it, on
  a name a SELECT then refuses in the very words the node is refused in. So both halves of the
  shape question are answered. The probe grew a fifth name to produce it, written into the
  account's subscription file because this server refuses a SUBSCRIBE of a name no mailbox has, and
  it is a registered pair like the other four. The flag name stays in `_NOT_A_MAILBOX` and the
  comment now says what kind of evidence it is: the plain `LIST "" "*"` that `folder.list()` sends
  cannot contain the word on a conformant server, and the Bridge answers an extended LIST with
  `BAD`, so reading it is a defence against a server not yet met rather than a live path.
