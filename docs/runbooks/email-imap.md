# Runbook: read-only email over ProtonMail Bridge

Bring up the read-only IMAP MCP server against a live ProtonMail Bridge and check it. This needs
your own Bridge running with your account and its generated credentials, which cannot live in CI
or in the repo. Design: [ADR-0009](../adr/ADR-0009-tools-mcp.md); module contract:
[brain-email.md](../modules/brain-email.md). Every answer either server gives is recorded in
[IMAP server answers](../readings/imap-server-answers.md).

## Prerequisites on the Windows host

ProtonMail Bridge running with IMAP enabled (default `127.0.0.1:1143`, STARTTLS), and the Bridge
username and generated password from Bridge, your account, Mailbox configuration.

## Supply the credentials, never in the repo

Put them in a gitignored file outside the repo, `~/.cortex/email.env`:

```
CORTEX_EMAIL_IMAP_HOST=127.0.0.1
CORTEX_EMAIL_IMAP_PORT=1143
CORTEX_EMAIL_IMAP_USER=<bridge username>
CORTEX_EMAIL_IMAP_PASSWORD=<bridge generated password>
CORTEX_EMAIL_IMAP_TLS_INSECURE=true   # accept the Bridge self-signed cert on loopback
```

To verify the certificate instead, export the Bridge TLS certificate from its settings and set
`CORTEX_EMAIL_IMAP_CA_CERT` to its path.

## Run the email integration tests

From WSL, `127.0.0.1` reaches the Windows Bridge only if WSL2 mirrored networking is on;
otherwise use the Windows host IP (`ip route show default | awk '{print $3}'`). Then:

```
set -a; . ~/.cortex/email.env; set +a
cd brain && uv run pytest -m integration --no-cov packages/email
```

`--no-cov` is required, or the workspace's 100% coverage threshold fails the run. The suite lists
your folders, searches INBOX, and reads a message through `EmailReader` over the real Bridge.
Reads are non-destructive: EXAMINE with `mark_seen=False` never touches your mail.

Four of those tests are worth selecting on their own, and all four should be re-run after a Bridge
upgrade, because each reads the server's own words and a Bridge that reworded a `NO` changes what
the model is told.

- `-k criterion` is the guard on what `search_emails` tells a model its `query` may say. It runs
  one query per criterion family the field description names, and fails if the description names a
  criterion the queries never ran. It also asserts that a query the Bridge answers `BAD` reaches
  the model as `SearchRefusedError`, naming the query and pointing at the dialect, with imaplib's
  own `UID command error: BAD [...]` left on the chained cause.
- `-k folder` is the guard on the other guess those tools invite. It asserts that every shape of a
  name no mailbox has is refused identically, as `FolderUnknownError` naming the folder and
  pointing at `list_folders`, out of both tools that take one, and that the offered list is exactly
  the names this server opens. The classification reads the server's own words (`no such mailbox`,
  since this Bridge sends no RFC 5530 response code), so a reworded `NO` would report a missing
  folder as a mailbox that could not answer, which is the safe direction but the wrong sentence.
- `-k uid` selects two rows. The read row finds one folder holding mail and one holding none,
  asserts that `fetch` answers `None` for a uid no message has in both and for every string that is
  not a uid, and asserts the premise the adapter reads absence off: this Bridge answers a `UID
  FETCH` of such a uid with `OK` and no data in both kinds of folder, which RFC 3501 defines as a
  uid no message has. It exists because the same Bridge answers the `UID` search imap-tools sends
  before its own fetch with `NO no such message` in a folder holding no mail, so the adapter sends
  the FETCH itself. The search row asserts that a search naming a uid in an empty folder answers
  with nothing found, and asserts both premises raw.

```
set -a; . ~/.cortex/email.env; set +a
cd brain && uv run pytest -m integration --no-cov packages/email/tests/test_email_live.py -k criterion
```

## The sidecar's own texts through the brain's wiring

Those refusals are what the brain re-stamps `Trust.TRUSTED`, so a `send_email` after one of them
reaches the confirmation card instead of the taint block. The email suite's live rows measure the
adapter; this one measures the whole path from the Bridge to that decision, with the sidecar
running as its own process and the registry built by `build_tool_registry`:

```
set -a; . ~/.cortex/email.env; set +a
export CORTEX_EMAIL_IMAP_TLS_INSECURE=true
cd brain && uv run pytest -m integration --no-cov -s \
  packages/orchestrator/tests/test_own_texts_bridge_live.py
```

The module starts the sidecar itself on port 9100 and stops it at the end, so bring any other
`cortex_email` down first or the bind fails. Nothing is sent: the send row runs with a confirmer
that declines, and it asserts the model reads `USER_DECLINED_MSG` rather than `DENIED_MSG`, which
is the whole live claim of the overlay. Enable the send path (`CORTEX_EMAIL_SEND_ENABLED=true` plus
the SMTP credentials, below) to run that row at all; without it the row skips, since a read-only
sidecar advertises no `send_email`. Which folders the rows use is discovered rather than named,
because whether the account has a folder holding no mail is a property of the account: the
not-found row runs in a folder holding mail and again in one holding none, and both come back
trusted.

## The other thing a refused SELECT can mean

The Bridge refuses every wrong name in the same words and all nineteen folders it lists open, so
a mailbox that is listed, real and shut is measured against a local Dovecot instead:
[imap-probe.md](imap-probe.md).

## Bring up the sidecar, end to end

```
set -a; . ~/.cortex/email.env; set +a
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.email.yml up
```

The sidecar reaches the Bridge via `host.docker.internal:1143` and serves the read-only tools at
`http://mcp-email:9100/mcp`; the brain runs with `CORTEX_TOOLS_BACKEND=mcp` pointed at it
(`CORTEX_TOOLS_ENDPOINTS__EMAIL`). A turn that needs email calls `list_folders`, `search_emails`
or `read_email`, each audited, and the result is fed back to the model. A real model that emits
tool calls also needs the GPU compose up. `read_email` returns readable text extracted from
HTML-only mail, falling back to the raw HTML only when nothing extracts.

To run the filesystem tools at the same time, layer the tools override too. Each override
contributes its own `CORTEX_TOOLS_ENDPOINTS__<name>` key and the brain aggregates both sidecars
behind one registry ([tools-mcp.md](tools-mcp.md)):

```
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.tools.yml -f docker/docker-compose.email.yml up
```

Tear down with `down` in place of `up` on the same file list.

## The send path is opt-in and needs approval

`send_email` is the write twin, SMTP over the same Bridge, default `127.0.0.1:1025`, STARTTLS, same
credentials. It is off by default and the sidecar registers it only under
`CORTEX_EMAIL_SEND_ENABLED=true`. On the brain side the composition root marks it as needing
approval (`CORTEX_TOOLS_GATED`, whose default already covers `send_email`), so an untainted turn's
send prompts the overlay confirmation card and a tainted turn's send is denied outright
([ADR-0022](../adr/ADR-0022-email-write-confirmer.md)). The sender authenticates as the Bridge user
and always sends as that address; `From` is not a parameter. Add to `~/.cortex/email.env`, where
the SMTP password is the same generated one:

```
CORTEX_EMAIL_SEND_ENABLED=true
CORTEX_EMAIL_SMTP_HOST=127.0.0.1
CORTEX_EMAIL_SMTP_PORT=1025
CORTEX_EMAIL_SMTP_USER=<bridge username>
CORTEX_EMAIL_SMTP_PASSWORD=<bridge generated password>
CORTEX_EMAIL_SMTP_TLS_INSECURE=true   # or CORTEX_EMAIL_SMTP_CA_CERT, as for IMAP
```

A draft can have `cc` and `bcc`, an `html` alternative, and `attachments`. An attachment is text
the assistant wrote (`{"filename": "notes.md", "content": "...", "subtype": "markdown"}`, composed
as a `text/<subtype>` part), never a file read off disk: the sidecar has no mount and no file-read
capability, so the confirmation card always shows the payload itself rather than a name for it. A
send is refused with a readable error if a filename is empty, contains a newline or exceeds 128
characters; if a subtype is not a MIME token; if there are more than 8 attachments; or if their
content totals more than 32768 characters.

The live round-trip test really sends one message between the two `example.com` test addresses,
with a cc, an HTML alternative and an attachment it parses back off IMAP, and confirms arrival over
IMAP. Point `CORTEX_EMAIL_LIVE_SEND_TO` at the second address and run the integration suite:

```
set -a; . ~/.cortex/email.env; set +a
export CORTEX_EMAIL_LIVE_SEND_TO=<the second example.com address>
cd brain && uv run pytest -m integration --no-cov packages/email
```

The compose override passes the `CORTEX_EMAIL_SMTP_*` and `SEND_ENABLED` variables through to the
sidecar with host `host.docker.internal`, so the same `.env` drives the end-to-end stack. With send
left disabled the sidecar is byte for byte the read-only server.
