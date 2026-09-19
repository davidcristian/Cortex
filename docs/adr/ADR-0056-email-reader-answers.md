# ADR-0056: What the email reader answers

**Status:** Accepted (2026-09-15)

## Context

The email sidecar's read tools, `list_folders`, `search_emails` and `read_email`
([ADR-0009](ADR-0009-tools-mcp.md) decision 6), are the model's only view of a mailbox, and every
argument they take is one a model guesses: the search dialect, a folder name, a uid. A wrong guess
costs a dispatch, and an answer that reads like a broken mailbox when the model could have fixed the
call sends it round a loop or ends the turn early. Every answer from an untrusted tool also taints
the turn and blocks the outbound tools behind it ([ADR-0013](ADR-0013-untrusted-content.md)), unless
it is text of the brain's own that the brain can mark trusted again.

The adapter is `ImapMailbox` over imap-tools, against the ProtonMail Bridge. The Bridge cannot
produce several of the answers the port has to classify (a mailbox listed and shut, a hierarchy node
that is not a mailbox, a declined read), so the second server those rules are measured against is a
Dovecot fixture this repo builds, [ADR-0057](ADR-0057-imap-probe-server.md). What both servers
answered, word for word, is in
[docs/readings/imap-server-answers.md](../readings/imap-server-answers.md).

## Decision

### The search

1. **The search dialect is described from a live run.** `query` reaches the server unaltered as raw
   IMAP `SEARCH` criteria. `SEARCH_QUERY_HELP` names only criteria the Bridge was measured accepting
   (the quoted-argument keys, the date keys in `dd-Mon-yyyy`, the standalone flags,
   `LARGER`/`SMALLER`, and `OR`, `NOT` and parentheses) and names the client syntax
   (`from:someone@example.com`) as refused. `KEYWORD` stays out, having been refused. An
   `integration`-marked test in `test_email_live.py` runs one query per criterion family named and
   fails when the description names one it never ran, so a word cannot be added to the prose without
   proof. `FOLDER_HELP` says a name comes word for word from `list_folders`; `SEARCH_LIMIT_HELP`
   says the matches kept are the first in the folder's uid order, which is not the newest.
2. **A refused search in a folder holding no mail is answered from its count.** `search` reads the
   message count off the EXAMINE it already sends (`folders.select`), and answers a refused search
   with nothing found when that count is zero: a folder holding nothing matches no criteria, so the
   answer is true without reading the refusal. A refusal in a folder holding mail, or one whose
   count the server did not report, stays the base error. The search is still sent: the Bridge
   refuses only a `UID` key there, answering every other criterion normally, and a malformed query
   is still refused as one.

### The port's own failures

3. **The port declares its own error types** in `cortex_email/errors.py`, since the sidecar cannot
   import the core: `MailboxError` (the mailbox could not answer), and two narrower facts under it,
   `SearchRefusedError` (holds the `query`; its message points at the field description, since a
   rewrite fixes it) and `FolderUnknownError` (holds the `folder`; its message names `list_folders`,
   since one call fixes it). `_translated` wraps every library failure, so no imap-tools or imaplib
   exception reaches a caller, and a correction's message includes no fragment of the wire answer.
4. **A search is refused only on a `BAD`.** imaplib raises `IMAP4.error` for a tagged `BAD` and its
   subclass `IMAP4.abort` when the connection goes away; `_search_failure` tests for the abort
   first, which becomes a `MailboxError` saying the connection dropped, because reporting an abort
   as a refusal would start a rewrite loop that cannot end.
5. **A correction is answered as a tool result, not raised.** A tool that lets an exception out is
   restated by FastMCP as `Error executing tool ...`, which is true of a mailbox that could not
   answer and false of a call the server read and declined. So the tools catch `SearchRefusedError`
   and `FolderUnknownError` and answer a `CallToolResult` with `isError` set and the text untouched;
   `McpToolRegistry` restates nothing.

### Folders

6. **A folder is reported missing only on evidence in the answer.** A `NO` to `SELECT` covers both a
   name no mailbox has and a mailbox that is there and shut. `folders.select` raises
   `FolderUnknownError` only when the refusal contains one of `_FOLDER_MISSING_PHRASES` (each
   server's measured wording, `no such mailbox` and `mailbox doesn't exist`) or
   `_FOLDER_MISSING_CODES` (RFC 5530's `[NONEXISTENT]` and `[CANNOT]`, matched with their brackets
   so prose cannot imitate a code). Anything else is the base error. That is the safe direction:
   sending a model to `list_folders` over a folder it read off `list_folders` is a loop, while "the
   mailbox could not answer" is true either way.
7. **`[CANNOT]` is a folder correction.** It is Dovecot's answer to a name no mailbox could have
   (empty, a trailing or doubled separator, a `..` part), where the Bridge says `no such mailbox`
   for the same mistake. The correction owed is the same one call on either server, so the port
   types both alike rather than inventing a third error out of a difference in server wording.
8. **`list_folders` offers the names a caller may pass.** A name the server flags `\Noselect` or
   `\NonExistent` (case-folded) is opened once with EXAMINE on the listing's own connection and
   dropped only when the refusal is the missing-folder evidence of decision 6; one function,
   `_says_folder_missing`, serves both paths. An unflagged name is never opened, and a listed
   mailbox that is shut stays on the list, flagged or not. The flag alone is not believed, because
   the two servers mean different things by it: Dovecot flags a hierarchy node it refuses, and the
   Bridge flags `Folders` and `Labels`, which open. The cost is one round trip per flagged name and
   none on an ordinary mailbox. The port's promise, checked by the contract, is that no offered name
   is one a later call would report unknown.
9. **`\NonExistent` is read though neither server sends it to this listing.** imap-tools sends the
   plain `LIST "" "*"`, and RFC 5258 returns the word only under a selection option; the Bridge has
   no LIST-EXTENDED at all. Reading it costs one comparison, and not reading it would offer an
   unopenable name on the first server met that sends it.

### Reading a message

10. **A read by uid sends one `UID FETCH` and reads absence off its answer.** `ImapMailbox.fetch`
    opens the folder first, then sends `UID FETCH <uid> (BODY.PEEK[] UID FLAGS RFC822.SIZE)` itself
    (`uidfetch.py`, through `box.client`) and answers `None` on an `OK` with no data, which RFC 3501
    section 6.4.8 defines as a uid no message has. Every other status is raised, so a `NO` reaches
    the model as a mailbox that could not answer: a message that cannot be shown absent is not
    reported absent. imap-tools' own fetch was dropped because it sends a `UID SEARCH` first, and
    the Bridge refuses that search with `NO` in a folder holding no mail.
11. **A uid is checked against RFC 3501's grammar before anything is sent.** `is_uid` accepts a
    decimal number with no leading zero from 1 to 4294967295; anything else is answered `None` with
    no command sent, because the two servers read a malformed uid differently (the Bridge reads `01`
    as 1 and `1:*` as a set).
12. **`UID_HELP` says what a uid is:** the number in square brackets at the start of a
    `search_emails` line, copied digit for digit; a name for a message only within the folder it was
    listed in; and a not-found answer is final for that folder.
13. **The not-found answer includes its correction.** `NOT_FOUND` in `values.py` is a template over
    `uid` and `folder` stating the fact, the per-folder rule, and the call that fixes it (search the
    folder again and copy a uid). The brain restates the same sentence in `own_texts.py` and marks
    it trusted again on byte equality (ADR-0013); the cross-tree registry
    (`scripts/emailcouplings.py`) compares the two declarations and checks that the server uses the
    constant rather than a second copy of the text.
14. **A call that ran and found nothing is not a failed call.** The not-found answer and the empty
    search (`(no matching messages)`) are unmarked; the two corrections are marked `failed`. The
    corrections are calls the server declined before touching a message; the not-found answer is a
    FETCH that ran against a folder holding nothing under that uid. So an audit reading over `ok`
    counts calls declined, not answers that corrected the model, and a reader who wants corrections
    reads the results.

### The contract

15. **The `Mailbox` port has one contract, run over every implementation.**
    `tests/mailbox_contract.py` runs over the fake, over `ImapMailbox` against a stand-in imap-tools
    box (`imap_stub.py`), and over the live probe. A condition no method can arrange is a field of
    `MailboxUnderTest` each fixture is built over: a refused search, a folder that will not open, a
    hierarchy node, a folder holding no mail (`empty_folder`), and a declined read (`declined_uid`).
    The stand-in answers in the measured servers' shapes, so a rule dropped from the adapter fails
    the contract's `imap` run, not only a unit test.
16. **Live evidence has two suites.** `test_email_live.py` runs against the Bridge: the criteria
    check, and a folder case that selects every listed name itself and asserts the offered list is
    exactly the set that opened. `test_imap_probe_live.py` runs against the probe. Both are
    `integration`-marked, outside the coverage requirement and never run in CI.

## Consequences

- A model that invents a folder, writes client search syntax, or reuses a uid across folders is
  corrected in words that name the fix, on either server, and those answers do not taint the turn.
- The keep branch of decision 8 is proved live only against the Bridge, on one account, since the
  probe flags a name that opens only in an `LSUB`, which is not the listing this adapter makes
  ([R-400](../refinements/tasks/400-the-keep-in-the-adapters-listing-is-one-account.md)).
- The folder rule reads text that includes the name the caller sent, which Dovecot echoes after
  `Mailbox doesn't exist:`; no shut refusal measured on either server echoes a name
  ([R-386](../refinements/tasks/386-the-answer-read-holds-the-name-that-was-sent.md)).
- `search` materializes imap-tools' fetch generator, so one message the server will not read, among
  the first `limit` matches, refuses the whole search
  ([R-570](../refinements/tasks/570-a-search-of-a-folder-holding-one-unreadable-message-is-refused-whole.md)).
  The search path's dropped-connection answer is driven by a scripted abort only
  ([R-673](../refinements/tasks/673-the-search-paths-dropped-connection-is-driven-by-no-live-row.md)).
- On the cortex tier the model copies a listed uid with or without `UID_HELP`, so the description is
  not what produces the copying; that measurement asked where copying is easiest
  ([R-584](../refinements/tasks/584-the-uid-rows-are-measured-where-the-listing-answers-the-ask.md)).

## Alternatives rejected

- **Omitting every flagged name**, which withheld the Bridge's `Folders` and `Labels`, and **opening
  every listed name**, a round trip per folder on every listing.
- **Passing selectability across the port**: a folder value every implementation fills and a
  rendering decision in the tool, for a consumer that needs only names it can pass.
- **Dropping a flagged name on any refusal**: it hides a folder that exists while the unflagged shut
  mailbox beside it stays listed.
- **Reading absence off a `NO`'s words, off the EXAMINE count, or off a `STATUS` or `SEARCH ALL`
  first**: the first learns one server's sentence for a command no longer sent, the second answers
  only the empty folder, the third costs a round trip to learn what the FETCH says.
- **Answering an empty folder's search without sending it**: it hid a refused query as an empty
  result and emptied the live criteria check on an account whose `INBOX` holds no mail.
- **Marking the not-found answer failed**, alone or with the empty search: the first moves the
  inconsistency, the second records an empty mailbox as a tool failure.

## Related

- [ADR-0009](ADR-0009-tools-mcp.md) (the sidecar), [ADR-0013](ADR-0013-untrusted-content.md) (the
  brain's own texts), [ADR-0022](ADR-0022-email-write-confirmer.md) (the send path),
  [ADR-0057](ADR-0057-imap-probe-server.md) (the probe).
- Readings: [imap-server-answers](../readings/imap-server-answers.md).
- Module: [brain-email](../modules/brain-email.md); runbook:
  [email-imap](../runbooks/email-imap.md).
