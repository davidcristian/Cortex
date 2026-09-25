# Runbook: keep the recall trail in a file

The recall trail's log line (`memory.recall`, read as described in
[memory-pgvector.md](memory-pgvector.md)) lives as long as the container's log driver keeps it.
Setting `CORTEX_MEMORY_RECALL_AUDIT_FILE` to a path makes the brain also append one JSON object per
recall to that file, after writing the log line. The path turns the trail on by itself:
`CORTEX_MEMORY_RECALL_AUDIT` need not be set as well, and the log line is always written first, so
a record the file could not keep is still on the log (ADR-0038 decision 5). The memory compose
override passes the variable through by name with no value, so the file is off unless you set it on
the host.

## What a record holds

The same fields the log line prints and no more: the conversation and turn, `query_chars` and never
the query, `pool`, `available`, `k`, `basis`, `keys_comparable`, `hits` (each kept memory's `id`,
`score`, `key` and `tainted`), `dropped` (each passed-over candidate's `id` and `score`),
`dropped_omitted` and `at`. No memory text is written. `dropped` is the list the log line prints,
bounded at 20 before either sink sees it, with `dropped_omitted` counting the rest.

A value the log line prints whole is kept as JSON. A value the line cuts past 2,048 characters, or
cannot print as JSON at all, such as a `NaN` score, is kept as the line's own text, a string. At the
shipped widths both lists fit under the cut, but test the type before reading into one:

```bash
jq -c 'select(.hits | type == "array") | .hits[].id'
```

## Where the file goes

The brain runs as uid 10001, and the file must be somewhere that user can write and that outlives
the container. The same volume the tool trail's file uses works, for the reason
[tools-mcp.md](tools-mcp.md) gives under "Keep the audit in a file". An override file of your own,
kept outside this repo, looks like this:

```yaml
services:
  brain:
    environment:
      CORTEX_MEMORY_RECALL_AUDIT_FILE: /home/cortex/recall-audit.jsonl
    volumes:
      - cortex-home:/home/cortex
volumes:
  cortex-home:
```

Add it with one more `-f` after the files you already layer, then read it with `jq`:

```bash
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.gpu.yml -f docker/docker-compose.memory.yml -f <your override> \
  exec -T brain cat /home/cortex/recall-audit.jsonl | jq -c 'select(.turn_id == "<turn id>")'
```

`select(.session_id == "<chat id>")` gives one conversation's recalls and
`select(.dropped_omitted > 0)` every recall that dropped more candidates than `dropped` lists. The
file is created with mode `0600`, because a record names which memories a conversation recalled.

## Gaps and rotation

A record that could not be appended is on the log line all the same, followed by a
`cortex_memory.audit_file` warning, `memory.recall.gap`, whose `error` says why, with `path` and
`turn_id` beside it. A file with gaps is incomplete rather than wrong, and the log lines of that
period are the complete record.

Nothing rotates or deletes the file. The sink opens it again for every record, so rotating is a
`mv`, or `logrotate` without `copytruncate`, and the next recall creates a fresh file. A record torn
by a full disk stays on its own line, and `jq -R 'fromjson? // empty'` reads past it.
