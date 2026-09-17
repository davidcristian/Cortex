# brain/packages/email (`cortex_email`)

**Purpose.** A standalone email MCP server: **read-only IMAP by default** (ADR-0009), plus an
**opt-in SMTP send tool** (ADR-0022). It offers three read tools (list folders, search, read one
message) and, only under `CORTEX_EMAIL_SEND_ENABLED=true`, the `send_email` write tool, over an MCP
streamable-http endpoint against a ProtonMail Bridge. It is **not** part of the brain: it runs as
its own sidecar process and the brain reaches it as an ordinary MCP server through `cortex_tools`.
There the composition root marks `send_email` as needing confirmation (`CORTEX_TOOLS_GATED`), so
every send needs the user's approval and a send on a tainted turn is refused outright.

## Public contract

`__all__` is the API.

### Reading

- `EmailReader(mailbox: Mailbox)` is the read-only use case over the `Mailbox` port. `folders()`
  lists folder names, `search(folder, query, limit)` returns `EmailSummary`s, and
  `read(folder, uid)` returns the full `EmailDetail` or `None`. It parses raw RFC822 with the
  standard library `email` package, so the parsing is pure and fully tested with canned messages.
  The body prefers `text/plain`; an HTML-only message goes through `html.html_to_text` (ADR-0009
  decision 8: script and style dropped, block boundaries become line breaks, entities decoded,
  whitespace collapsed), keeping the raw HTML only when nothing extracts.
- `EmailSummary` and `EmailDetail` are frozen value types: a search hit and a full message.
- `Mailbox` is the `Protocol` the reader needs (`list_folders`, `search`, `fetch` to a `RawEmail`);
  the imap-tools adapter and a fake both satisfy it. Its promises are written in
  `tests/mailbox_contract.py`, driven over both:
  - It fails in exactly three ways, and every implementation owes all three.
  - **No name `list_folders` returns is one the other two calls would refuse as a folder no mailbox
    has**, so an implementation filters out a server's bare hierarchy nodes rather than passing them
    on (ADR-0056 decision 8). A listed mailbox that is there and will not open is outside that
    promise, so the list may hold one and does on the probe fixture. Two checks cover it, one
    walking the offered list and one requiring that naming a node anyway still fails. The other
    direction, that every name the server opens is offered, can only be seen beside the server's own
    LIST, so the adapter's tests and the live Bridge test cover it.
  - **`fetch` answers `None` for a uid no message has**, in a folder holding mail and in one holding
    none alike, and for a string that is not a uid, and it answers `None` **only** when the message
    is shown absent, so a read the server declined for a reason of its own stays `MailboxError`.
    Four checks cover that, including one for a folder holding none (`empty_folder`, which every
    fixture names, because a real server answered the two kinds differently one command down) and
    one for the round trip from a search line's uid back to that message (ADR-0056 decision 10). The
    declined read is measured on the probe's `Sealed`, a mailbox holding one message the mail
    process cannot open, where the FETCH is answered `NO [SERVERBUG] Internal error occurred`; the
    check reads the uid a fixture names as `declined_uid` (ADR-0057 decision 4).

### Errors

`MailboxError` says the mailbox could not answer: an unreachable Bridge, rejected TLS or login, a
folder that could not be examined, a dropped connection. Beneath it are two narrower subclasses, one
per argument the read tools invite a model to guess, split on whether writing the call differently
would change anything.

- `SearchRefusedError` is the server rejecting a query it read as malformed (ADR-0056 decision 3).
  It holds the `query` that was rejected and its message points the model at the `query` field's own
  description rather than restating the dialect.
- `FolderUnknownError` reports that no mailbox holds the folder that was named (ADR-0056 decision
  6). A name no mailbox *could* have is the same error rather than a third one: the two servers
  disagree about which fact an empty or malformed name is and cannot disagree about the correction
  (ADR-0056 decision 7). It holds the `folder` it was given and sends the model to `list_folders`.

Neither holds any part of the server's answer, those fragments being a wire command and a status the
model never sent; the cause chain keeps both for an operator.

### The IMAP adapter

`ImapMailbox(config)` is the `Mailbox` over imap-tools. It connects per call, so the server holds no
IMAP state.

- **Listing.** `list_folders` reads the LIST attributes `folder.list()` returns beside each name and
  treats a name flagged `\Noselect` (RFC 3501) or `\NonExistent` (RFC 5258), case-folded, as
  unproven: it opens that name once with EXAMINE and drops it only when the open is refused in the
  words or the code that prove no mailbox has the name. The two servers disagree about the flag,
  Dovecot rejecting such a node in the very words that prove a folder missing and the Bridge opening
  the two parents of its own hierarchy, so opening the name is correct on both (ADR-0056 decision
  8). Both flags are measured, in different listings: Dovecot sends `\Noselect` with its hierarchy
  node under every LIST it accepts, and keeps `\NonExistent` for a subscribed name no mailbox has,
  which only a LIST asking for subscriptions returns. Neither can appear in the plain `LIST "" "*"`
  that `folder.list()` sends, and the Bridge answers an extended LIST with `BAD`, so reading
  `\NonExistent` is a defence against a server not yet met (ADR-0056 decision 9).
- **Classifying a refusal.** No exception of the IMAP stack escapes the adapter: a `BAD` answer to a
  search becomes `SearchRefusedError`, a `NO` to `SELECT` whose own text says the mailbox does not
  exist becomes `FolderUnknownError`, and everything else, imaplib's `IMAP4.abort` for a connection
  lost mid-command included, becomes `MailboxError` with the cause chained. Both classifications
  read what the server said rather than assuming it, and the abort is tested by subclass, since
  reporting a dropped connection as a refused query would send a model round a rewrite loop that
  cannot end. The select is classified from either of two forms: `_FOLDER_MISSING_PHRASES` holds the
  Bridge's measured `no such mailbox` and Dovecot's measured `Mailbox doesn't exist`, and
  `_FOLDER_MISSING_CODES` holds the RFC 5530 codes `[NONEXISTENT]` and `[CANNOT]`. Those two, the
  predicate that reads them and the two calls that open a folder are `folders.py`; `imap.py` is the
  connection and the three port methods. The same `NO` also covers a folder that is really there and
  could not be opened, and **a folder that cannot be proved missing is not reported missing**. The
  code settles a refusal whose prose says nothing about a mailbox: Dovecot answers every malformed
  name (empty, `Parent/`, `/Parent`, `Parent//Child`, `INBOX/../etc`, `~root`) with
  `[CANNOT] Invalid mailbox name` where the Bridge says `no such mailbox` (ADR-0056 decision 7). It
  is read bracketed, so a refusal whose prose merely contains "cannot" is not read as a missing
  folder. The other refusal is `[NOPERM] Permission denied`, measured on a mailbox that is listed
  and shut (ADR-0057 decision 1).
- **A search the server refuses in a folder holding no mail answers with nothing found.** The Bridge
  refuses a `UID` search key in such a folder, `NO no such message`, which imap-tools raises out of
  the search it runs before any fetch, tainting a turn over a call nothing was wrong with. The
  evidence for the answer is the count the folder's own EXAMINE reported, which `folders.select`
  reads off the accepted answer and hands back: a folder holding no message matches no criteria,
  whatever the server's reason for refusing was. The search is still sent, because that is what has
  the server parse the query, so a malformed query in an empty folder is still `SearchRefusedError`.
  A folder whose count the server did not report is not answered this way, and neither is a refusal
  in a folder holding mail (ADR-0056 decision 2).
- **A read by uid is one `UID FETCH`, sent by `uidfetch.py` rather than through imap-tools'
  `fetch`.** imap-tools searches for the uid before fetching it, and the Bridge answers that search
  `NO no such message` for every uid in a folder holding no mail. RFC 3501 defines what a
  `UID FETCH` answers for a uid no message has, an `OK` with no data, and both servers answer
  exactly that in both kinds of folder, so absence is read off the FETCH's own answer and off
  nothing else. A `NO` to the FETCH is a read the server declined and stays `MailboxError` with the
  server's text. The uid is checked against RFC 3501's `uniqueid` grammar first (`is_uid`: a decimal
  number with no leading zero, at most 4294967295), and anything else is answered `None` with no
  command sent, because the Bridge reads `01` as 1 and `2,1` or `1:*` as a set that fetches messages
  the caller never named. The whole message is asked for with `BODY.PEEK[]`, the read that leaves
  the Seen flag alone (ADR-0056 decision 10).

### The tools

`build_server(reader, sender=None) -> FastMCP` registers the three read tools always, and
`send_email(to, subject, body, cc="", bcc="", html="", attachments=())` only when a sender is
passed, with advisory MCP `ToolAnnotations` (not read-only, destructive, open-world) that are never
the authority on confirmation. `cc` and `bcc` are comma-separated address lists, `html` adds a rich
alternative, and `attachments` is an array of `{filename, content, subtype}` objects.

**The advertised schema is generated, never written**, so what the model is told is whatever
`values.py` and the tool signature say; the server tests assert the generated schema itself. The
model-facing prose lives in `values.py` (ADR-0056 decision 1). `SEARCH_QUERY_HELP` names the raw
IMAP `SEARCH` dialect the query is written in, criterion by criterion and only where a live pass
against a real Bridge proved the criterion works, plus the client `from:` syntax that is rejected
rather than parsed. `FOLDER_HELP` (used by `read_email` too, so the two cannot disagree) says a
folder name comes exactly as `list_folders` gave it, and `FOLDER_UNKNOWN` is the same fact said once
the server has rejected a name. `UID_HELP` says a uid is the number in square brackets on a
`search_emails` line, copied digit for digit, that it names a message only in the folder it was
listed in, and that a not-found answer is final (ADR-0056 decision 12); `NOT_FOUND` says that last
fact again once the read came back empty (ADR-0056 decision 13). `SEARCH_LIMIT_HELP` says the
matches kept are the first in the folder's own uid order rather than the newest. The live test
`test_every_advertised_search_criterion_is_one_the_bridge_accepts` guards that prose: it runs one
query per named family and fails if the description names a criterion no query ran.

**Each tool answers with a single readable text block**, two of them building it into a
`CallToolResult` themselves (`_one_text`). Both folder-taking tools mark a correction `isError`
while keeping the port's own wording, because a tool that lets an exception out is restated by
FastMCP as `Error executing tool <name>: ...`, which is accurate for a mailbox that could not answer
(deliberately left to escape) and inaccurate for a call the server read and declined.
`search_emails` catches both corrections and `read_email` the folder one. The not-found answer is
deliberately unmarked, and so is a search with no hits: `isError` says whether the server ran the
call, not whether the answer corrects the model (ADR-0056 decision 14). The brain negates this flag
into the audit trail's `ToolInvocation.ok`; what recovers the corrections is the same line's
`trust`, since the brain's own-text overlay re-stamps two of them trusted, the not-found answer and
the empty search (ADR-0009 decision 16).

**`read_email` adds a result `_meta`** (`_SOURCE_META_KEY`, `"cortex/source"`) declaring the message
sender as `{"kind": "sender", "value": <From>}` (`_sender_source`, omitted when there is no `From`).
The `_meta` sits beside the text, so the model-facing content is unchanged; the brain's tool
registry reads the key and decides trust, taking a claimed, sanitized source and never a label. This
is the producer half of the sidecar declaration channel (ADR-0027 decision 9), a wire contract with
`cortex_tools` that this standalone sidecar cannot import, so `scripts/crosscheck.py` compares this
module's bindings with `cortex_tools`'s, each module's use of them, and both contracts' quotations
(`scripts/emailcouplings.py`, ADR-0042). The kind word is bound here as `_SENDER_KIND`, because the
brain writes it only as the enum member `SourceKind.SENDER`, which the scan cannot read as a
declaration. The two field names are bound on both sides as (`_KIND_FIELD`, `"kind"`) and
(`_VALUE_FIELD`, `"value"`).

`main()` reads the environment config, builds the reader (and an `SmtpSender` only when
`SmtpConfig.enabled`), and runs the server over streamable-http (`python -m cortex_email`).

### Sending

- `EmailDraft` is the frozen send-side value the user approves: `to`, `subject` and `body` plus
  optional `cc`, `bcc`, `html` (each defaulting to `""`, meaning omitted) and `attachments`. It is
  the extension point: a further shape is a new field here, never a change to `EmailSender.send`.
- `EmailAttachment(filename, content, subtype="plain")` is one attached file, composed as a
  `text/<subtype>` part. The main type is not a parameter, exactly as `From` is not: the tool
  attaches text the assistant **wrote**, never bytes it read, which is what keeps the confirmation
  card showing the payload rather than a name for it (ADR-0022 decision 10). It is also **the one
  value type here that is a prompt**: pydantic lifts its class docstring into the tool's `$defs`
  entry and each field's `Field(description=...)` into that field, so `values.py` owns that
  model-facing prose (ADR-0022 decision 12). The three bounds a send is checked against
  (`MAX_ATTACHMENTS`, `MAX_ATTACHMENT_CHARS`, `MAX_FILENAME_CHARS`) live there too, beside
  `ATTACHMENTS_HELP`, so the number the model is told and the number `SmtpSender` enforces are one
  value.
- `EmailSender` is the `Protocol` the send tool needs (`send(draft: EmailDraft) -> str`). Every
  implementation owes three things and `tests/sender_contract.py` drives both over them. A draft
  `drafts.refuse_unsendable` rejects raises its `ValueError` and nothing is handed over: a CR or LF
  in the recipient, subject, `cc`, `bcc` or an attachment filename (header injection, not left to
  the interpreter's patch level), an empty or overlong filename, a `subtype` that is not a MIME
  token (`_SUBTYPE_TOKEN`), more than `MAX_ATTACHMENTS` (8), or `content` totalling more than
  `MAX_ATTACHMENT_CHARS` (32768) characters, all refused rather than truncated. A send that reached
  nobody raises `SendError`. A send the server accepted for some recipients answers the
  `drafts.confirmation` line, which names the recipient and the subject, with the refused addresses
  appended. Both implementations call the same two functions, so the fake cannot accept a draft the
  adapter would refuse (ADR-0068 decision 5).
- `SendError` is the sender's one failure type, a sibling of `MailboxError` rather than a subclass.
  It keeps smtplib's own text, which is the only thing saying why, and never holds the password,
  which reaches smtplib only as a `login` argument.
- `SmtpSender(config)` is the `EmailSender` over smtplib with STARTTLS or implicit TLS, connecting
  per call. `From` is the authenticated Bridge user, never a parameter, so the tool cannot forge a
  sender. A `bcc` is in the envelope but is stripped from the transmitted message by `send_message`,
  so it stays hidden from the To and Cc readers. An `html` draft composes a `multipart/alternative`
  (plain `body` fallback plus HTML), a plain draft stays a single `text/plain` part, and attachments
  wrap either in a `multipart/mixed`. It wraps every `smtplib.SMTPException` and `OSError` into
  `SendError`, and reads the refused recipients out of the dict `send_message` returns.

### Configuration

`EmailConfig` holds the `CORTEX_EMAIL_IMAP_*` settings: host, port, user, password (`SecretStr`),
`security` (`starttls` or `ssl`), and `ca_cert` and `tls_insecure` for the Bridge's self-signed
certificate. The defaults target a local Bridge (127.0.0.1:1143, STARTTLS). `SmtpConfig` holds
`CORTEX_EMAIL_SMTP_*` plus `CORTEX_EMAIL_SEND_ENABLED`, defaulting to the Bridge SMTP loopback
(127.0.0.1:1025, STARTTLS) with the same certificate escape hatches; enabling send without
credentials fails at startup. **Two of these defaults are module constants rather than literals
inside the fields**, `DEFAULT_TLS_INSECURE` (which both halves read) and `DEFAULT_SEND_ENABLED`,
because the email compose override states each again as a substitution default and
`scripts/crosscheck.py` can only compare a restatement with a declaration it can read (ADR-0042).
Change both or neither.

## Read-only by default, in three layers on the read path

Without the explicit send opt-in, only read tools register; folders are opened with EXAMINE
(`readonly=True`, never SELECT); and fetches never set the Seen flag (`mark_seen=False` on a search,
`BODY.PEEK[]` on a read by uid). The IMAP path cannot modify a mailbox. The one write capability,
`send_email` over SMTP on a different protocol and connection, exists only when deliberately
enabled, and the brain requires the user's confirmation for it (ADR-0022).

## Invariants

- A standalone sidecar that depends on no other cortex package; the brain reaches it over MCP.
- Real IMAP work is `ImapMailbox`, validated against a live Bridge; the parsing and the tools are
  pure and covered 100% without a server.
- Fully typed, pyright strict clean, 100% line and branch over fakes: a fake `Mailbox` for the
  reader and tools (`tests/mailbox_fake.py`), a stand-in imap-tools `MailBox` for `ImapMailbox`
  (`tests/imap_stub.py`), a fake `EmailSender` (`tests/sender_fake.py`) and a stand-in smtplib
  (`tests/smtp_stub.py`), each shared so one fixture drives every suite. Both mailbox fakes keep
  their canned mail in the first folder they list and answer every other folder as holding none, and
  the stand-in answers a `UID FETCH` by uid the way the two measured servers do, so the contract's
  read-by-uid checks drive both kinds of folder over one fixture.
- The live contract is the `integration`-marked `tests/test_email_live.py`, run per
  [docs/runbooks/email-imap.md](../runbooks/email-imap.md). The Dovecot probe fixture
  (`tests/test_imap_probe_live.py` over `docker/docker-compose.imap-probe.yml`, ADR-0057) builds its
  mailboxes from `docker/dovecot/probe-mailboxes.sh`; the suite's eight fixture names and one uid
  are module constants that `scripts/crosscheck.py` compares with the lines that script writes them
  in, since that suite never runs in CI.
- Fixed to the MCP SDK v1.x (`mcp>=1.23,<2`).

**Dependencies.** mcp (the FastMCP server), imap-tools (the IMAP client, STARTTLS-capable through
the standard library `imaplib`, which the Bridge defaults to), pydantic (the `Field` descriptions
the tool schema is generated from) and pydantic-settings. Deployed by
`docker/docker-compose.email.yml`.
