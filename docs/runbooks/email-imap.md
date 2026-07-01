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
`http://mcp-email:9100/mcp`; the brain runs with `CORTEX_TOOLS_BACKEND=mcp` pointed at it. A turn
that needs email calls `list_folders`/`search_emails`/`read_email`, each audited, and the result
is fed back to the model (a real model that emits tool calls also needs the GPU compose + `--jinja`).

## Teardown

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.email.yml down
```
