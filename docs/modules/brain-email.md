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
  the imap-tools adapter and a fake both satisfy it.
- `ImapMailbox(config)` is the `Mailbox` over imap-tools. Connects per call (the Bridge is local)
  so the server holds no IMAP state.
- `EmailConfig` holds env-driven settings (`CORTEX_EMAIL_IMAP_*`): host/port/user/password
  (`SecretStr`), `security` (starttls|ssl), and `ca_cert` / `tls_insecure` for the Bridge's
  self-signed cert. Defaults target a local Bridge (127.0.0.1:1143, STARTTLS).
- `EmailSummary` / `EmailDetail` are frozen value types (a search hit; a full message).
- `EmailDraft` is the frozen send-side value the user approves: `to`/`subject`/`body` plus
  optional `cc`, `bcc`, `html` (each defaulting to `""` = omitted), and `attachments`. It is the
  seam's extension point: a further shape is a new field here, never a change to the
  `EmailSender.send` signature.
- `EmailAttachment(filename, content, subtype="plain")` is one attached file, composed as a
  `text/<subtype>` part. The maintype is not a parameter, exactly as `From` is not: the tool
  attaches text the assistant **wrote**, never bytes it read, which is what keeps the
  confirmation card showing the payload rather than a name for it (ADR-0022 attachments
  addendum).
- `build_server(reader, sender=None) -> FastMCP` registers the three read tools always, and
  `send_email(to, subject, body, cc="", bcc="", html="", attachments=())` only when a sender is
  passed (with advisory MCP `ToolAnnotations`: not read-only, destructive, open-world, and never
  authority; the brain-side overlay is). `cc`/`bcc` are comma-separated address lists; `html`
  adds a rich alternative; `attachments` is an array of `{filename, content, subtype}` objects
  (the one nested schema in the tool surface). Each tool returns a single readable string, with
  one exception: `read_email` returns a `CallToolResult` wrapping that same text block plus a
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
  token, there are at most `MAX_ATTACHMENTS` (8), and their `content` totals at most
  `MAX_ATTACHMENT_CHARS` (32768) characters. Returns one readable confirmation line.
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
  reader/tools, a fake imap-tools `MailBox` for `ImapMailbox`. The live contract is the
  `integration`-marked `tests/test_email_live.py` (run per docs/runbooks/email-imap.md).
- Pinned to the MCP SDK v1.x (`mcp>=1.23,<2`).

**Dependencies.** mcp (the FastMCP server), imap-tools (the IMAP client, STARTTLS-capable via
stdlib `imaplib`, which the Bridge defaults to), pydantic-settings (env config). Deployed by
`docker/docker-compose.email.yml`.
