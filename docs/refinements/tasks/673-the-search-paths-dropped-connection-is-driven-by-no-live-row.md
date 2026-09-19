# The search path's dropped connection is driven by no live row

**Status:** open, fix when it bites
**Area:** email
**Trigger:** the brain image moves off Python 3.12 (`FROM python:3.12-slim-trixie` in
`brain/Dockerfile`, the image the email sidecar runs) or imap-tools moves off 1.13.0 in
`brain/uv.lock`, since which class a dropped connection raises is those libraries' choice and the
unit row scripts the class itself; or a search on a real server drops its connection and comes
back as `SearchRefusedError`, sending a model to rewrite a query that was never the problem.
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-09-19

Opened 2026-09-15 by the close of
[569](569-the-dropped-read-under-dovecots-default-is-measured-by-hand-and-driven-by-no-live-row.md),
which declined a live row for words no classification reads and left the half that is a
classification standing.

`_search_failure` in `brain/packages/email/src/cortex_email/imap.py` reads the type of what
imaplib raised: a plain `IMAP4.error` is the server refusing to parse the query, which crosses the
port as `SearchRefusedError` and tells the model to write the search again, and its `IMAP4.abort`
subclass is a connection that went away mid-command, which must never come back as that, because
rewriting a good query cannot end the loop. The abort branch is driven by one unit test scripting
`IMAP4.abort("socket error: EOF")`, the text imaplib itself raises for a socket closed without a
`BYE`. The row chooses the class, so it holds the classification and says nothing about which
class a real drop raises.

A real server does produce it. Measured on 2026-09-15 against the probe restarted with
`imap_fetch_failure` at its default `disconnect-immediately`, a search of `Sealed` answers
`* BYE FETCH failed: Internal error occurred` and drops the connection, which reaches the port as
`MailboxError: the mailbox connection dropped during that search`, the abort branch taken on a
live answer. Under the `no-after` the probe's configuration sets, the same search is a tagged `NO`
instead and the branch is never reached.

**Why it was left.** The classification is fail-safe in the direction that matters: both answers
are a `MailboxError` a model reads as a mailbox that could not answer, and the branch decides only
whether it is also told to rewrite the query. The unit row holds the subclass check, so the
mistake this guards against fails a gate today, against a scripted answer rather than a measured
one.

**What would close it.** A second probe service on the same image with `imap_fetch_failure` left
at its default, or a second user whose setting differs, plus a row that searches the sealed
message through the port and asserts the base error rather than a refusal. The second-user route
was tried on 2026-09-15 and does not work on dovecot 2.3.21: a `passwd-file` userdb entry
carrying `imap_fetch_failure=disconnect-immediately` as an extra field resolves the home and is
dropped before `doveadm user` prints it, so the session keeps the global setting. The service
route costs a published port and a second address for `just email-folder-probe` to find, which is
the cost weighed and declined for the words in the entry that opened this one.

## Trail

- 2026-09-15: opened by the close of
  [569](569-the-dropped-read-under-dovecots-default-is-measured-by-hand-and-driven-by-no-live-row.md),
  which measured the abort live and settled that the words behind it need no row while the
  classification reading its type still has none.
- 2026-09-19: the code claims held and the trigger was repaired, because as written it could not
  fire under the libraries the sidecar runs. Read in the installed Python 3.12.3 imaplib, every
  raise on a lost connection is `IMAP4.abort`: the `BYE` check, a socket error sending a command
  or a literal, an EOF or an unterminated line on read, and the rewrap at command completion. A
  socket error while reading escapes imaplib as the `OSError` it is and reaches `_translated` as
  the base `MailboxError`. The one plain
  `IMAP4.error` on the read path is an over-long line, which is not a drop. So a drop reaching
  `SearchRefusedError` needs a library change or an edit to `_search_failure`, and the unit row
  `test_a_connection_lost_mid_search_is_not_reported_as_a_refusal` fails on the edit; the
  trigger now names the library versions, which neither `brain/Dockerfile` nor `brain/uv.lock`
  has moved since this entry was opened. The same row's comment said a search of a folder holding
  no mail is answered from its count and never reaches the server, which was the design the
  2026-09-15 change wrote first and rejected: the search is still sent, and running the row's
  shape over an empty folder raised the same dropped-connection `MailboxError`. The comment is
  corrected in `brain/packages/email/tests/test_imap.py`.
