# Runbook for read-only email over ProtonMail Bridge (Slice 6 host half)

Bring up the read-only IMAP MCP server against a live ProtonMail Bridge and validate it. This is
the **host-driven** half of the email tool. It needs *your* Bridge running with *your* account
and its generated credentials, which cannot live in CI or the repo. The server, parsing, and
config are built and 100%-covered without a server. Design: [ADR-0009](../adr/ADR-0009-tools-mcp.md);
module: [brain-email.md](../modules/brain-email.md).

## Prerequisites (on the Windows host)

- ProtonMail Bridge running with IMAP enabled (default `127.0.0.1:1143`, STARTTLS).
- The Bridge username + generated password (Bridge → your account → Mailbox configuration).

## Supply the credentials (never in the repo)

Put them in a gitignored file **outside** the repo, `~/.cortex/email.env`:

```
CORTEX_EMAIL_IMAP_HOST=127.0.0.1
CORTEX_EMAIL_IMAP_PORT=1143
CORTEX_EMAIL_IMAP_USER=<bridge username>
CORTEX_EMAIL_IMAP_PASSWORD=<bridge generated password>
CORTEX_EMAIL_IMAP_TLS_INSECURE=true   # accept the Bridge self-signed cert on loopback
```

To verify the cert instead of `tls_insecure`, export the Bridge TLS certificate (Bridge →
Settings) and set `CORTEX_EMAIL_IMAP_CA_CERT` to its path.

## Run the email integration test (host-side)

From WSL, `127.0.0.1` reaches the Windows Bridge only if WSL2 mirrored networking is on;
otherwise use the Windows host IP (`ip route show default | awk '{print $3}'`). Then:

```
set -a; . ~/.cortex/email.env; set +a
cd brain && uv run pytest -m integration --no-cov packages/email
```

`--no-cov` matters. The 100% gate in the workspace addopts would otherwise fail the run. It
lists your folders, searches INBOX, and reads a message through `EmailReader` over the real
Bridge (the IMAP the fake cannot prove). Reads are non-destructive: EXAMINE + `mark_seen=False`
never touch your mail.

## Bring up the sidecar + end-to-end

```
set -a; . ~/.cortex/email.env; set +a
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.email.yml up
```

The sidecar reaches the Bridge via `host.docker.internal:1143` and serves the read-only tools at
`http://mcp-email:9100/mcp`; the brain runs with `CORTEX_TOOLS_BACKEND=mcp` pointed at it
(`CORTEX_TOOLS_ENDPOINTS__EMAIL`). A turn that needs email calls
`list_folders`/`search_emails`/`read_email`, each audited, and the result is fed back to the
model (a real model that emits tool calls also needs the GPU compose + `--jinja`). `read_email`
returns readable text extracted from HTML-only mail (ADR-0009 refinements addendum), falling
back to the raw HTML only when nothing extracts.

To run the **filesystem tools at the same time**, layer the tools override too. Each override
contributes its own `CORTEX_TOOLS_ENDPOINTS__<name>` key and the brain aggregates both sidecars
behind one registry ([tools-mcp.md](tools-mcp.md)):

```
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.tools.yml -f docker/docker-compose.email.yml up
```

## Teardown

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.email.yml down
```

## The send path (Slice 8.8, ADR-0022) is opt-in, gated, confirmed

`send_email` is the write twin (SMTP over the same Bridge, default `127.0.0.1:1025`,
STARTTLS, same credentials). It is **off by default**. The sidecar registers it only under
`CORTEX_EMAIL_SEND_ENABLED=true`. Brain-side it is stamped `gated` by the composition
root (`CORTEX_TOOLS_GATED`, default already covers `send_email`), so an untainted turn's send
prompts the overlay confirmation card and a tainted turn's send is denied outright
([ADR-0022](../adr/ADR-0022-email-write-confirmer.md)). The sender authenticates as the
Bridge user and always sends as that address. `From` is not a parameter.

Add to `~/.cortex/email.env` (the Bridge SMTP password is the same generated one):

```
CORTEX_EMAIL_SEND_ENABLED=true
CORTEX_EMAIL_SMTP_HOST=127.0.0.1
CORTEX_EMAIL_SMTP_PORT=1025
CORTEX_EMAIL_SMTP_USER=<bridge username>
CORTEX_EMAIL_SMTP_PASSWORD=<bridge generated password>
CORTEX_EMAIL_SMTP_TLS_INSECURE=true   # or CORTEX_EMAIL_SMTP_CA_CERT, as for IMAP
```

The live round-trip test really sends one message between the two `example.com` test
addresses and verifies arrival back over IMAP; point `CORTEX_EMAIL_LIVE_SEND_TO` at the
second address and run the integration suite as above:

```
set -a; . ~/.cortex/email.env; set +a
export CORTEX_EMAIL_LIVE_SEND_TO=<the second example.com address>
cd brain && uv run pytest -m integration --no-cov packages/email
```

The compose override passes the `CORTEX_EMAIL_SMTP_*`/`SEND_ENABLED` env through to the
sidecar (host `host.docker.internal`), so the same `.env` drives the end-to-end stack; with
send left disabled the sidecar is byte-for-byte the read-only Slice 6 server.
