# Runbook: reading the brain's logs

What a rendered log line contains, what it never contains, and how to search one.
`docker compose logs brain` is where every diagnosis in these runbooks ends up. Bringing the brain
up: [local-dev-wsl.md](local-dev-wsl.md). Decision:
[ADR-0051](../adr/ADR-0051-log-line-rendering.md).

A line has the fields the code attached to it rather than the message alone:

```text
brain-1  | INFO:cortex_orchestrator.server:gRPC server listening host=0.0.0.0 port=50051
```

Everything after the message is `key=value` pairs in name order, which is what makes two lines of
the same kind comparable column by column and what makes `grep "capped=True"` work. Three reading
rules: a scalar is written the way Python writes it, so a boolean reads `True` and not `true`; a
value containing whitespace or a quote is quoted (`error="permission denied"`), so it stays one
field; and anything structured is compact JSON (`hits=[{"id":"m1","score":0.87}]`), so it can be
pasted into `jq`.

**The message says what happened and the fields say what it happened to**, so a value appears once
on the line. A message is a constant sentence: `started a model process model=cortex pid=41
port=8081`, never that sentence with `model=cortex pid=41 port=8081` written into it as well. That
is what lets the greps in these runbooks match on a message's words and read the values out of the
fields beside them, and it is why `docker compose logs brain | grep "could not be asked"` finds
every control call the sidecar left unanswered, however many tiers and errors they name. Two kinds
of line still have a value in their prose: one whose message the code also raises as an
exception's text, which has to read on its own where no formatter runs, and one whose sentence
needs a word to finish it (`a tier of the baseline residency could not be started`).

**Two things never appear in a rendered line**, and the formatter removes them rather than each
call site. A field whose name looks like a secret (`token`, `password`, `secret`, `credential`,
`api_key`, `authorization`, `cookie`, and anything containing one of those) prints `<redacted>` in
place of its value, with the key still there so a withheld field reads differently from a missing
one. The same names are withheld inside a structured field, so a tool call's `arguments` prints
`{"password":"<redacted>"}` for a key the model named `password`, and a structure nested too deep
to read through prints `<redacted>` whole. And the credential inside any URL is stripped from the
whole line, message and traceback included, so a `redis://` or `imap://` connection error names
its host and never its password.

For a deployment that collects lines rather than reading them, `CORTEX_LOG_FORMAT=packed` writes
one JSON object per line instead, with the fields under their own `fields` key:

```sh
CORTEX_LOG_FORMAT=packed docker compose up -d --build
docker compose logs brain | sed 's/^brain-1  | //' | jq -c 'select(.fields.model)'
```

The sidecar has its own half of the same setting, `CORTEX_MODELHOST_LOG_FORMAT`, under its own
container's prefix. A name neither build knows fails the process at startup rather than falling
back to a rendering nobody asked for, so a typo is loud.

The two per-line trails worth knowing about are the tool audit (`cortex.tools.audit`, always on,
[tools-mcp.md](tools-mcp.md)) and the recall trail (`cortex.memory.recall`, behind
`CORTEX_MEMORY_RECALL_AUDIT`, [memory-pgvector.md](memory-pgvector.md)). Both write a bare message
and put everything in fields.

A reply the output guardrail removed a link from logs one line when it settles, with a count per
reason and the policy set by `CORTEX_OUTPUT_GUARDRAIL`, and never the link or its host:

```text
INFO:cortex_core.turn_output:the output guardrail removed links from this reply collected=<links taken from untrusted results> link=<links taken on a strict or image turn> lookalike=<links only a non-ASCII host took> policy=<redact, lookalike or strict>
```

Each link is counted once, under the first reason that took it, so under `policy=lookalike` the
sum of `lookalike=` over a week is how many links that policy removed beyond the default's. A
reply that lost nothing logs nothing.

