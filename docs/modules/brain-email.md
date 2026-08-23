# brain/packages/email (`cortex_email`)

**Purpose.** A standalone email MCP server: **read-only IMAP by default** (ADR-0009), plus an
**opt-in SMTP send twin** (ADR-0022). It exposes three read tools (list folders, search, read
one message) and, only under `CORTEX_EMAIL_SEND_ENABLED=true`, the `send_email` write tool,
over an MCP streamable-http endpoint against a ProtonMail Bridge. It is **not** the brain: it
runs as its own sidecar process, and the brain reaches it as an ordinary MCP server through
`cortex_tools`. There `send_email` is stamped `gated` by the composition-root overlay
(`CORTEX_TOOLS_GATED`), so every send needs the user's approval and a tainted turn's send is
denied outright.

**Public contract** (everything importable from `cortex_email`; `__all__` is the API):

- `EmailReader(mailbox: Mailbox)` is the read-only use-case over the `Mailbox` port. `folders()`
  lists folder names; `search(folder, query, limit)` returns `EmailSummary`s; `read(folder, uid)`
  returns the full `EmailDetail` or None. It parses raw RFC822 with the stdlib `email` package
  (canonicalized headers), so the parsing is pure and fully tested with canned messages. The
  body prefers `text/plain`; an HTML-only message goes through `html.html_to_text` (ADR-0009
  refinements addendum, via stdlib `HTMLParser`: script/style dropped, block boundaries become
  line breaks, entities decoded, whitespace collapsed), keeping the raw HTML only when nothing
  extracts (e.g. an image-only body), so the body is never empty when the message has one.
- `Mailbox` is the `Protocol` the reader needs (`list_folders`, `search`, `fetch` → `RawEmail`);
  the imap-tools adapter and a fake both satisfy it. It fails in exactly three ways and every
  implementation owes all three, the fake included, which is what the shared contract
  (`tests/mailbox_contract.py`, driven over the fake and the adapter) exists to hold. It also owes
  one promise about success: every name `list_folders` answers with is a name the other two calls
  may be given, so a server's bare hierarchy nodes are filtered out by the implementation rather
  than handed on (ADR-0022 hierarchy-node addendum). Two contract checks hold it, one walking the
  offered list and one saying that naming a node anyway is still refused. The other direction, that
  every name the server opens is offered, is not a contract check: it can only be seen beside the
  server's own LIST, so the adapter's tests and the live Bridge test carry it (ADR-0022
  flagged-and-refused addendum).
- `MailboxError` says the mailbox could not answer: unreachable Bridge, refused TLS or login, a
  folder that could not be examined, a connection that went away. Beneath it are the two narrower
  subclasses, one per argument the read tools invite a model to guess, and the line in both cases
  is whether writing the call differently would change anything.
  `SearchRefusedError` is the server having read a query and refused it as malformed (ADR-0022
  refused-search addendum). It carries the `query` it refused and its message points the model at
  the `query` field's own description rather than restating the dialect.
  `FolderUnknownError` is no mailbox having the folder that was named (ADR-0022 unknown-folder
  addendum), and a name no mailbox *could* have is the same error rather than a third one: the
  two servers disagree about which fact an empty or malformed name is and cannot disagree about
  the correction, since `list_folders` never offered such a name (ADR-0022 refused-name addendum).
  It carries the `folder` it was given and sends the model to `list_folders`, the
  cheaper correction of the two: one call rather than a rewrite. Neither carries any part of the
  server's answer, those fragments (`UID command error: BAD [b'[Error offset=38]: expected
  space']`; `Response status "OK" expected, but "NO" received. Data: [b'no such mailbox']`) being
  a wire command and a command status the model never sent. The cause chain keeps both for an
  operator.
- `ImapMailbox(config)` is the `Mailbox` over imap-tools. Connects per call (the Bridge is local)
  so the server holds no IMAP state. `list_folders` reads the LIST attributes `folder.list()`
  carries beside each name and treats a name flagged `\Noselect` (RFC 3501) or `\NonExistent`
  (RFC 5258), case-folded, as a question rather than an answer: it opens that name once with
  EXAMINE and drops it only if the server refuses it too. The two servers disagree about the flag,
  Dovecot refusing such a node in the very words that prove a folder missing and the Bridge opening
  the two parents of its own hierarchy, so asking is what is correct on both (ADR-0022
  flagged-and-refused addendum). Both spellings are measured, in different listings: Dovecot sends
  `\Noselect` with its hierarchy node under every LIST it accepts, and keeps `\NonExistent` for a
  subscribed name no mailbox has, which only a LIST asking for subscriptions returns. The plain
  `LIST "" "*"` that `folder.list()` sends can carry neither that name nor that word, and the
  Bridge answers an extended LIST with `BAD`, so reading the newer spelling is a defence against a
  server not yet met rather than a live path (ADR-0022 newer-spelling addendum).
  No exception of the IMAP stack escapes it: a `BAD` answer to
  a search becomes `SearchRefusedError`, a `NO` to `SELECT` whose own text says the mailbox does
  not exist becomes `FolderUnknownError`, and everything else, imaplib's `IMAP4.abort` for a
  connection lost mid-command included, becomes `MailboxError` with the cause chained. Both
  classifications look rather than assume, and for the same reason. The abort is tested for by
  subclass, since reporting a dropped connection as a refused query would send a model round a
  rewrite loop that cannot end. The select is classified from what the server said, in either of
  the two forms it can say it in: `_FOLDER_MISSING_PHRASES` holds the Bridge's measured `no such
  mailbox` and Dovecot's measured `Mailbox doesn't exist`, and `_FOLDER_MISSING_CODES` holds the
  RFC 5530 codes `[NONEXISTENT]` and `[CANNOT]`. The same `NO` also covers a folder that is
  really there and could not be opened, and a folder that cannot be proved missing is not
  reported missing. Two servers, one fact, no shared word and no response code from either for
  the missing case, which is why the words are read at all and why there are two of them; the
  code is what settles the refusal whose prose says nothing about a mailbox, Dovecot answering
  every malformed name (empty, `Parent/`, `/Parent`, `Parent//Child`, `INBOX/../etc`, `~root`)
  with `[CANNOT] Invalid mailbox name` where the Bridge says `no such mailbox` (ADR-0022
  refused-name addendum). It is read bracketed rather than as the word inside it, so a refusal
  whose prose merely contains "cannot" is untouched. The other
  refusal is `[NOPERM] Permission denied`, measured on a mailbox that is listed and shut (ADR-0022
  two-server addendum, `tests/test_imap_probe_live.py` over `docker/docker-compose.imap-probe.yml`).
- **The probe suite's seven fixture names are module constants and registered couplings.**
  `GUARDED_FOLDER`, `REAL_FOLDER`, `NOSELECT_PARENT`, `NODE_CHILD`, `FEIGNED_FOLDER` and
  `FOLLOWED_SUBSCRIPTION` name mailboxes `docker/dovecot/probe-mailboxes.sh` builds, and
  `GHOST_SUBSCRIPTION` names the one it does not:
  a subscription written into the account's own file with no mailbox behind it, which is the only
  way that server sends `\NonExistent`. The last two are a pair: `FEIGNED_FOLDER` opens, and
  carries `\Noselect` in an `LSUB` of `%` only because `FOLLOWED_SUBSCRIPTION` under it is
  subscribed and it is not, which is the one way this server says what the Bridge says in its
  ordinary LIST (ADR-0022 flagged-name-that-opens addendum).
  `scripts/crosscheck.py` ties each to the line
  the script writes it in (ADR-0029 fixture addendum). This suite is `integration`-marked and
  never runs in CI, so the gate is the only thing that would notice the fixture and the suite
  drifting apart; the invented name the suite expects to be refused is deliberately not tied,
  the point of it being that nothing builds it.
- `EmailConfig` holds env-driven settings (`CORTEX_EMAIL_IMAP_*`): host/port/user/password
  (`SecretStr`), `security` (starttls|ssl), and `ca_cert` / `tls_insecure` for the Bridge's
  self-signed cert. Defaults target a local Bridge (127.0.0.1:1143, STARTTLS).
- **Two of these defaults are module constants rather than literals inside the fields**,
  `DEFAULT_TLS_INSECURE` (which both halves read) and `DEFAULT_SEND_ENABLED`, because the email
  override spells each again as a substitution default and `scripts/crosscheck.py` can only hold a
  restatement to a declaration it can read (ADR-0029's boolean addendum). Flip both or neither.
  One name covers the reader's hatch and the sender's because it is one answer rather than two
  that coincide: a hatch that ships open is not a hatch.
- `EmailSummary` / `EmailDetail` are frozen value types (a search hit; a full message).
- `EmailDraft` is the frozen send-side value the user approves: `to`/`subject`/`body` plus
  optional `cc`, `bcc`, `html` (each defaulting to `""` = omitted), and `attachments`. It is the
  seam's extension point: a further shape is a new field here, never a change to the
  `EmailSender.send` signature.
- `EmailAttachment(filename, content, subtype="plain")` is one attached file, composed as a
  `text/<subtype>` part. The maintype is not a parameter, exactly as `From` is not: the tool
  attaches text the assistant **wrote**, never bytes it read, which is what keeps the
  confirmation card showing the payload rather than a name for it (ADR-0022 attachments
  addendum). It is also **the one value type in this package that is a prompt**: pydantic lifts
  its class docstring into the tool's `$defs` entry and each field's `Field(description=...)`
  into that field, so `values.py` imports pydantic and owns the model-facing prose (ADR-0022
  per-field addendum). The three bounds a send is refused against (`MAX_ATTACHMENTS`,
  `MAX_ATTACHMENT_CHARS`, `MAX_FILENAME_CHARS`) live there too, beside `ATTACHMENTS_HELP`, so
  the number the model is told and the number `SmtpSender` enforces are one value.
- `build_server(reader, sender=None) -> FastMCP` registers the three read tools always, and
  `send_email(to, subject, body, cc="", bcc="", html="", attachments=())` only when a sender is
  passed (with advisory MCP `ToolAnnotations`: not read-only, destructive, open-world, and never
  authority; the brain-side overlay is). `cc`/`bcc` are comma-separated address lists; `html`
  adds a rich alternative; `attachments` is an array of `{filename, content, subtype}` objects
  (the one nested schema in the tool surface), carrying `ATTACHMENTS_HELP` as its own schema
  description because the two bounds it names belong to the array rather than to any field of
  an attachment. `search_emails` describes all three of its parameters from `values.py`
  (ADR-0022 search-dialect addendum): `SEARCH_QUERY_HELP` names the raw IMAP `SEARCH` dialect
  the query is written in, criterion by criterion and only where a live pass against a real
  Bridge proved the criterion works, plus the client `from:` syntax that is refused rather than
  understood; `FOLDER_HELP` (spent by `read_email` too, so the two cannot drift) says a folder
  name comes verbatim from `list_folders`, and `FOLDER_UNKNOWN` is the same fact said once the
  server has refused a name, so it names neither searching nor reading in particular; `SEARCH_LIMIT_HELP` says the matches kept are the
  first in the folder's own uid order rather than the newest. The live test
  `test_every_advertised_search_criterion_is_one_the_bridge_accepts` is the guard on that prose:
  it runs one query per named family and fails if the description names a criterion no query
  ran, and it asserts that the client syntax comes back as `SearchRefusedError` carrying the
  query. Each tool answers with a single readable text block. Two of them build that block into
  a `CallToolResult` themselves (`_one_text`), each for something the block alone cannot carry.
  Both folder-taking tools mark a correction `isError` while keeping the port's own wording,
  because a tool that lets an exception out is restated by FastMCP as `Error executing tool
  <name>: ...`, which is the truth for a mailbox that could not answer (deliberately left to
  escape) and a falsehood for a call the server read and declined. `search_emails` catches both
  corrections, `read_email` the folder one, which it hits before it has looked at a uid (so a
  guessed folder never reads "message not found"). `read_email` adds a
  result `_meta` (`_SOURCE_META_KEY`, `"cortex/source"`) declaring the message sender
  (`{"kind": "sender", "value": <From>}`, `_sender_source`, omitted when there is no `From`). The
  `_meta` rides beside the text, so the model-facing content is unchanged; the brain's tool
  registry reads the key and decides trust (a claimed, sanitized source, never a label). This is
  the producer half of the sidecar declaration channel (ADR-0027 sidecar addendum), a
  cross-deployable wire contract with `cortex_tools` that this standalone sidecar cannot import.
  Covered in-process via `FastMCP.call_tool`. `main()` reads the env config,
  builds the imap-tools reader (and an `SmtpSender` only when `SmtpConfig.enabled`), and runs
  the server over streamable-http (`python -m cortex_email`).
- `EmailSender` is the `Protocol` the send tool needs (`send(draft: EmailDraft) -> str`).
- `SmtpSender(config)` is the `EmailSender` over smtplib + STARTTLS (or implicit TLS),
  connecting per call. `From` is the authenticated Bridge user, never a parameter, so the tool
  cannot spoof a sender; a CR/LF in the recipient, subject, `cc`, or `bcc` is refused in code
  (header injection, not left to the interpreter's patch level). A `bcc` rides the envelope but
  is stripped from the transmitted message by `send_message`, so it stays hidden from the To/Cc
  readers. An `html` draft composes a `multipart/alternative` (plain `body` fallback + HTML);
  a plain draft stays a single `text/plain` part. Attachments wrap whatever the body shapes
  built in a `multipart/mixed`, and are refused (never truncated) unless each filename is
  non-empty, CR/LF-free, and at most `MAX_FILENAME_CHARS` (128), each `subtype` is a MIME
  token (`_SUBTYPE_TOKEN`, the one of the four bounds that stays here because it is a rule
  rather than a number), there are at most `MAX_ATTACHMENTS` (8), and their `content` totals at
  most `MAX_ATTACHMENT_CHARS` (32768) characters. The three numbers are imported from
  `values.py`, which spends them in the schema the model reads. Returns one readable
  confirmation line.
- `SmtpConfig` holds env-driven settings (`CORTEX_EMAIL_SMTP_*` + `CORTEX_EMAIL_SEND_ENABLED`):
  defaults target the Bridge SMTP loopback (127.0.0.1:1025, STARTTLS) with the same
  cert-verification escape hatches as IMAP; enabling send without credentials fails fast at
  startup.

**Read-only by default, in three layers on the read path.** Without the explicit send opt-in,
only read tools register; folders are opened with EXAMINE (`readonly=True`, never SELECT); and
fetches never set the Seen flag (`mark_seen=False`). The IMAP path can never modify a mailbox.
The one write capability (`send_email`, SMTP on a different protocol and connection) exists only
when deliberately enabled, and is gated + confirmed brain-side (ADR-0022).

**Invariants.**
- Standalone sidecar that depends on no other cortex package; the brain reaches it over MCP.
- Adapter-only I/O: the real IMAP work is `ImapMailbox` (integration-tested against a live
  Bridge); the parsing + tools are pure and 100%-covered without a server.
- Fully typed, pyright strict clean; 100% line+branch over fakes, namely a fake `Mailbox` for the
  reader/tools (`tests/mailbox_fake.py`) and a stand-in imap-tools `MailBox` for `ImapMailbox`
  (`tests/imap_stub.py`), each shared so the same one drives every suite. Both `Mailbox`
  implementations are run through `tests/mailbox_contract.py`, which is where the port's promises
  are written, both corrections among them, including that a folder which failed to open for any
  other reason is never reported missing. The live contract is the `integration`-marked
  `tests/test_email_live.py` (run per docs/runbooks/email-imap.md).
- Pinned to the MCP SDK v1.x (`mcp>=1.23,<2`).
- The advertised schema is **generated, never written**, so what the model is told about an
  attachment is whatever `values.py` and the tool signature say. The server tests assert the
  generated schema itself (every attachment field described, the array's two bounds spelled
  from the constants), which is the only place that coupling is checked.

**Dependencies.** mcp (the FastMCP server), imap-tools (the IMAP client, STARTTLS-capable via
stdlib `imaplib`, which the Bridge defaults to), pydantic (the `Field` descriptions the tool
schema is generated from) and pydantic-settings (env config). Deployed by
`docker/docker-compose.email.yml`.
