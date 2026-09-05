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

`--no-cov` matters, since the 100% gate in the workspace addopts would otherwise fail the run. The
suite lists your folders, searches INBOX, and reads a message through `EmailReader` over the real
Bridge (the IMAP the fake cannot prove). Reads are non-destructive: EXAMINE + `mark_seen=False`
never touch your mail.

One of those tests is the guard on what `search_emails` tells a model its `query` may say
(ADR-0022 search-dialect addendum): it runs one query per criterion family the field description
names, and fails if the description names a criterion the queries never ran. Run it after any
Bridge upgrade, because a criterion the server stops accepting becomes a refusal the model has to
work back from, and this is the only place that shows up. The same test asserts what a refusal
looks like: a query the Bridge answers `BAD` reaches the model as `SearchRefusedError`, naming the
query and pointing at the dialect, with imaplib's own `UID command error: BAD [...]` left on the
chained cause where an operator reading a traceback finds it (ADR-0022 refused-search addendum):

```
set -a; . ~/.cortex/email.env; set +a
cd brain && uv run pytest -m integration --no-cov packages/email/tests/test_email_live.py -k criterion
```

Its sibling is the guard on the other guess those tools invite, the `folder` (ADR-0022
unknown-folder addendum). It asserts that every shape of a name no mailbox has is refused
identically, as `FolderUnknownError` naming the folder and pointing at `list_folders`, out of both
tools that take one; and that the offered list is exactly the names this server opens, walking its
own LIST to check both directions, so nothing the description tells a model to use comes back as
the refusal it warns about and no name that works is withheld. Run it after any Bridge
upgrade too: the classification reads the server's own words (`no such mailbox`, since this
Bridge sends no RFC 5530 response code), so a Bridge that reworded its `NO` would start reporting
a missing folder as a mailbox that could not answer, which is the safe direction but the wrong
sentence:

```
set -a; . ~/.cortex/email.env; set +a
cd brain && uv run pytest -m integration --no-cov packages/email/tests/test_email_live.py -k folder
```

The third live row is the read by uid (ADR-0022 fetch-by-uid addendum). It finds one folder of
the account holding mail and one holding none, asserts that `fetch` answers `None` for a uid no
message has in both and for every string that is not a uid, and asserts the premise the adapter
reads absence off: this Bridge answers a `UID FETCH` of such a uid with `OK` and no data in both
kinds of folder, which RFC 3501 defines as a uid no message has. The row exists because the same
Bridge answers the `UID` search imap-tools sends before its own fetch with `NO no such message`
in a folder holding no mail, so the adapter sends the FETCH itself and never that search. Run it
after any Bridge upgrade too:

```
set -a; . ~/.cortex/email.env; set +a
cd brain && uv run pytest -m integration --no-cov packages/email/tests/test_email_live.py -k uid
```

Add `CORTEX_EMAIL_IMAP_TLS_INSECURE=true` when you are accepting the Bridge's self-signed cert on
loopback rather than verifying it with an exported `ca_cert`.

## The own texts through the brain's own wiring (ADR-0013 own-text addendum)

The refusals above are what the brain re-stamps `Trust.TRUSTED`, so a `send_email` after one of
them reaches the confirmation card instead of the taint block. The email suite's live rows measure
the adapter; this one measures the whole path from the Bridge to that decision, with the sidecar
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
is the whole live claim of the overlay. Enable the send path
(`CORTEX_EMAIL_SEND_ENABLED=true` plus the SMTP credentials, below) to run that row at all;
without it the row skips, since a read-only sidecar advertises no `send_email` to gate.

Which folders the rows use is discovered rather than named, because whether the account has a
folder holding no mail is a property of the account: the not-found row runs in a folder holding
mail and again in one holding none, and both come back trusted. Until the adapter fetched by uid
the second raised instead, because this Bridge answers the `UID` search imap-tools sent first
with `NO no such message` in such a folder, and the row recorded the taint (ADR-0022 fetch-by-uid
addendum). Re-run after a Bridge upgrade for the reason the folder row above is re-run: the answer
either side sends is what the classification reads.

## The IMAP probe: the other thing a refused SELECT can mean

A `NO` to `SELECT` covers two facts, a mailbox that does not exist and a mailbox that does and
cannot be opened, and this Bridge produces only the first: every wrong name is refused in the
same words and all nineteen folders it lists open. So the second is measured against a second
server, a Dovecot run locally for the purpose, whose ACL plugin can leave a mailbox listed, real,
and shut ([ADR-0022](../adr/ADR-0022-email-write-confirmer.md) two-server addendum). It holds
one message, sealed so that the mail process cannot read it, checks no password, publishes on
loopback only, and is nothing to do with the brain stack:

```
just up-imap-probe
just email-folder-probe
just down-imap-probe
```

Its LIST returns seven names, six of them mailboxes (`INBOX`, `Parent/Child`, `Feigned`,
`Feigned/Followed` and `Sealed`, which open, and `Guarded`, which does not) and one of them a
`\Noselect` node that is not a mailbox at all (`Parent`). An eighth name, `Ghost`, is subscribed
and not there, which no LIST returns and which exists only to make the server send
`\NonExistent`. What each is for is written in `docker/dovecot/probe-mailboxes.sh`, which builds
them. All eight are named a second time by `packages/email/tests/test_imap_probe_live.py`, as is
the uid of the one message `Sealed` holds, and
`scripts/crosscheck.py` holds the two spellings together (ADR-0029 fixture addendum): rename a
mailbox in the script alone and the gate says so on the next commit, where the suite that would
otherwise catch it is `integration`-marked and runs only when somebody measures.
The mail store is a tmpfs, so every start builds the tree again from nothing, and the path it sits
at is written once in `docker/docker-compose.imap-probe.yml` and handed to the container as
`CORTEX_IMAP_PROBE_MAIL_ROOT`, which the entrypoint reads and dovecot expands with `%{env:...}`
(ADR-0022 one-mail-root addendum). The configuration directory is a tmpfs too, handed over as
`CORTEX_IMAP_PROBE_CONFIG_ROOT`, because the image declares a volume there as well and a container
with nothing mounted at it leaves an anonymous volume behind on every single run; the conf is
bound in at `/probe.conf` and copied onto that mount by the entrypoint (ADR-0022
configuration-directory addendum). So a full `up` and `down` of this fixture leaves `docker volume
ls` exactly as it found it, which is worth checking after a Dovecot bump: a new declared volume in
the image would start leaking again. Two ways this fixture fails to start, both by design and
both naming themselves in `docker compose logs`: `is not the tmpfs the compose file mounts` means
one of the two mounts went missing, and `parameter not set` means the variable behind it never
arrived. A third, `gave up waiting for:`, means the first start of the server never produced its
auth socket or its stop never finished, the two waits the sealed message below needs. None is a
server fault, and `just up-imap-probe` reports each as a container that exited rather than as a
stack that came up.
The recipe reaches the server at the published port when that answers and at the container's own
address when it does not, which is what a Docker Desktop engine beside a WSL distro gives; a probe
that answers at neither is reported rather than waited on. The answers, measured through
`ImapMailbox` against `dovecot/dovecot:2.3.21` (build `47349e2482`) and verbatim, are:

| SELECT of | what the server answered |
| --- | --- |
| `Nonexistent`, and every other shape of wrong name | `NO Mailbox doesn't exist: Nonexistent (0.001 + 0.000 secs).` |
| `Guarded`, listed and ACL-shut | `NO [NOPERM] Permission denied (0.001 + 0.000 secs).` |
| `Parent`, a `\Noselect` node with a child | `NO Mailbox doesn't exist: Parent (0.001 + 0.000 secs).` |
| `""`, the empty name | `NO [CANNOT] Invalid mailbox name: Name is empty (0.001 + 0.000 secs).` |
| `Parent/`, and every other malformed shape | `NO [CANNOT] Invalid mailbox name: Ends with hierarchy separator (0.001 + 0.000 secs).` |

Four things to read off that. The refusal for a mailbox that is **there and shut** carries none
of the words that prove a folder missing, which is the assumption the whole classification rests
on and which nothing had measured before this. The refusal for a **missing** mailbox shares no word with the
Bridge's, so both phrases are read and neither server sends a response code to read instead. The
refusal for a name **no mailbox could have** says nothing about a mailbox at all, so it is read off
RFC 5530's `[CANNOT]` instead and typed as the folder correction, which is what the Bridge already
gave it through its ordinary `no such mailbox` (ADR-0022 refused-name addendum); this server sends
that code with six different reasons, one per way a name can be malformed. And
this server refuses a listed `\Noselect` node exactly as it refuses a name no mailbox has, where
the Bridge's own `\Noselect` parents open. Since the refusal carries nothing that could tell the
two apart, `list_folders` reads the LIST attributes imap-tools already carries beside each name and
opens anything flagged `\Noselect` or `\NonExistent` before deciding, dropping it only when this
server refuses it as well (ADR-0022 flagged-and-refused addendum). `Parent` goes, `Parent/Child` is
listed in its own right, and on the Bridge the two flagged parents that open are kept.

The probe is also the second server for the read by uid (ADR-0022 fetch-by-uid addendum), and one
of its rows records the two answers side by side. Every folder here but `Sealed` holds no mail,
and in one
`UID SEARCH UID 4294967290` answers `OK` with nothing found, where the Bridge answers
`NO no such message`; `UID FETCH 4294967290` answers `OK` with no data on both servers, which is
the one answer the adapter reads. A string that is not a uid is `BAD Invalid uidset` here for
`abc`, `0` and `4294967296` alike, where the Bridge answers the first two with its own `BAD` and
the third with no data, so the adapter holds the uid to RFC 3501's grammar itself rather than
asking either server.

`Sealed` is the one read this server declines (ADR-0022 declined-read addendum). It holds one
message whose dbox file the entrypoint makes unreadable to the mail process after saving it
through a first, loopback-only start of the server, and `docker/dovecot/probe.conf` sets
`imap_fetch_failure = no-after`, so the FETCH is answered with a tagged `NO` on a connection that
stays open rather than with Dovecot's default `* BYE` and a dropped connection. Measured through
the adapter's own `UID FETCH <uid> (BODY.PEEK[] UID FLAGS RFC822.SIZE)`, verbatim:

| `UID FETCH` of | what the server answered |
| --- | --- |
| `Sealed`'s message, under `no-after` | `NO [SERVERBUG] Internal error occurred. Refer to server log for more information. [2026-09-05 04:43:45] (0.001 + 0.000 secs).` |
| the same message, under the default `disconnect-immediately` | `* BYE FETCH failed: Internal error occurred. Refer to server log for more information.`, and the connection closed |
| a uid no message has, in the same folder | `OK` with no data |

The adapter reads only the last of those as a message that is not there; the first two reach it
as `MailboxError` carrying the server's words. The row that asserts it also asserts that the
folder is listed and the message is in it (`EXISTS 1`), that a search of the folder is refused
the same way, and that the connection survives the `NO`.

### Asking this server for the flag imap-tools never asks about

`folder.list()` sends the plain `LIST "" "*"`, so the newer attribute for "not a mailbox" cannot
reach the adapter through it. To see where that word really comes from, drive imaplib directly
against the running probe (this is what
`test_the_newer_spelling_of_unselectable_is_a_word_this_server_really_sends` does, so
`just email-folder-probe` runs it for you):

```python
conn.xatom("LIST", "(SUBSCRIBED)", '""', '"*"')
conn.response("LIST")   # ('LIST', [b'(\\Subscribed \\NonExistent) "/" Ghost'])
conn.xatom("LIST", '""', '"*"', "RETURN (CHILDREN)")
conn.response("LIST")   # Parent is still (\Noselect \HasChildren) here
```

`\NonExistent` arrives instead of `\Noselect` and never beside it, on the subscribed name rather
than on the node, and `Ghost` is refused by a SELECT in the same words `Parent` is. The Bridge
cannot be asked at all: it advertises no LIST-EXTENDED and answers the extended form with `BAD`
(ADR-0022 newer-spelling addendum).

### And for the flag that lies, which is why the flag is asked rather than believed

`list_folders` drops a flagged name only when the server also refuses it, because a `\Noselect`
name really can open. That was measured on the Bridge, on one account, and nowhere else until
`Feigned` was added to this fixture. `Feigned` is an ordinary mailbox that opens; its child
`Feigned/Followed` is subscribed and it is not, which is the state RFC 3501 has an `LSUB` of `%`
answer with `\Noselect` whatever the name really is. So the standard obliges a compliant server to
flag a mailbox that opens normally, and this one does:

```python
conn.lsub('""', '"%"')  # ('LSUB', [b'() "/" Ghost', b'(\\Noselect) "/" Feigned'])
conn.list()             # Feigned is (\HasChildren) here, and nothing else
conn.select('"Feigned"', readonly=True)   # ('OK', [b'0'])
```

The second line is the half that stays out of reach, and it is asserted too. In dovecot 2.3.21's
plain `LIST`, the one listing the adapter itself makes, the flag and the refusal are computed from
one fact, so no name can be flagged there and still open. Two configurations were tried against
2.3.21 to produce one and both failed: a second namespace whose prefix collides with a real
mailbox lists that name twice, once `(\Noselect \HasChildren)`, and a SELECT resolves to the
flagged reading and is refused; a namespace prefixed `INBOX/` is merged with the real INBOX and
listed `(\HasChildren)` with no flag at all. The Bridge's own test therefore stays the only live
proof of the keep in the listing the adapter makes (ADR-0022 flagged-name-that-opens addendum).

Rerun the probe after any change to the folder classification, and after a Dovecot bump if the
pinned image ever moves: the wordings above are the evidence the rule is built on, and a server
that reworded its `NO` is exactly what this measures.

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

A draft can carry `cc`/`bcc`, an `html` alternative, and `attachments`. An attachment is text
the assistant wrote (`{"filename": "notes.md", "content": "...", "subtype": "markdown"}`,
composed as a `text/<subtype>` part), never a file read off disk: the sidecar has no mount and
no file-read capability, deliberately, so the confirmation card always shows the payload
itself rather than a name for it (ADR-0022 attachments addendum). A send is refused with a
readable error if a filename is empty, carries a newline, or exceeds 128 characters; if a
subtype is not a MIME token; if there are more than 8 attachments; or if their content totals
more than 32768 characters.

The live round-trip test really sends one message between the two `example.com` test
addresses (with a cc, an HTML alternative, and an attachment it parses back off IMAP) and
verifies arrival back over IMAP; point `CORTEX_EMAIL_LIVE_SEND_TO` at the second address and
run the integration suite as above:

```
set -a; . ~/.cortex/email.env; set +a
export CORTEX_EMAIL_LIVE_SEND_TO=<the second example.com address>
cd brain && uv run pytest -m integration --no-cov packages/email
```

The compose override passes the `CORTEX_EMAIL_SMTP_*`/`SEND_ENABLED` env through to the
sidecar (host `host.docker.internal`), so the same `.env` drives the end-to-end stack; with
send left disabled the sidecar is byte-for-byte the read-only Slice 6 server.
