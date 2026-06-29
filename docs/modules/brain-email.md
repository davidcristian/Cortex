# brain/packages/email (`cortex_email`)

**Purpose.** A standalone **read-only** IMAP MCP server (ADR-0009). It exposes three read-only
email tools (list folders, search, read one message) over an MCP streamable-http endpoint,
backed by imap-tools against a ProtonMail Bridge. It is **not** the brain: it runs as its own
sidecar process, and the brain reaches it as an ordinary MCP server through `cortex_tools`.

**Public contract** (everything importable from `cortex_email`; `__all__` is the API):

- `EmailReader(mailbox: Mailbox)` is the read-only use-case over the `Mailbox` port. `folders()`
  lists folder names; `search(folder, query, limit)` returns `EmailSummary`s; `read(folder, uid)`
  returns the full `EmailDetail` or None. It parses raw RFC822 with the stdlib `email` package
  (canonicalized headers, plain-text body), so the parsing is pure and fully tested with canned
  messages.
- `Mailbox` is the `Protocol` the reader needs (`list_folders`, `search`, `fetch` → `RawEmail`);
  the imap-tools adapter and a fake both satisfy it.
- `ImapMailbox(config)` is the `Mailbox` over imap-tools. Connects per call (the Bridge is local)
  so the server holds no IMAP state.
- `EmailConfig` holds env-driven settings (`CORTEX_EMAIL_IMAP_*`): host/port/user/password
  (`SecretStr`), `security` (starttls|ssl), and `ca_cert` / `tls_insecure` for the Bridge's
  self-signed cert. Defaults target a local Bridge (127.0.0.1:1143, STARTTLS).
- `EmailSummary` / `EmailDetail` are frozen value types (a search hit; a full message).
- `build_server(reader) -> FastMCP` registers the three tools on a FastMCP server (covered
  in-process via `FastMCP.call_tool`). `main()` reads the env config, builds the imap-tools
  reader, and runs the server over streamable-http (`python -m cortex_email`).

**Read-only guarantee in three layers.** Only read tools are registered (no write tool exists);
folders are opened with EXAMINE (`readonly=True`, never SELECT); and fetches never set the Seen
flag (`mark_seen=False`). Nothing in this package can modify a mailbox.

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
`docker-compose.email.yml`.
