# The search path's dropped connection is driven by no live row

**Status:** open, fix when it bites
**Area:** email
**Trigger:** a search on a real server drops its connection and comes back as
`SearchRefusedError`, sending a model to rewrite a query that was never the problem.
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-09-15

Opened 2026-09-15 by the close of
[569](569-the-dropped-read-under-dovecots-default-is-measured-by-hand-and-driven-by-no-live-row.md),
which declined a live row for words no classification reads and left the half that is a
classification standing.

`_search_failure` in `brain/packages/email/src/cortex_email/imap.py` reads the type of what
imaplib raised: a plain `IMAP4.error` is the server refusing to parse the query, which crosses the
port as `SearchRefusedError` and tells the model to write the search again, and its `IMAP4.abort`
subclass is a connection that went away mid-command, which must never come back as that, because
rewriting a good query cannot end the loop. The abort branch is driven by one unit test scripting
`IMAP4.abort("socket error: EOF")`, a string no server sent.

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
