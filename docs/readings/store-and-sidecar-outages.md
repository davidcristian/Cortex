# Readings: Postgres, the embedding server and the file sidecar going away

What the person sees, and what the stores keep, when the memory store, the embedding server or the
filesystem sidecar stops, hangs or restarts between turns and during one. The flows the
[Redis, brain and cortex restarts](store-and-process-restarts.md) did not cover. The defects found
are filed as tasks, linked where each is described.

## The rig

**2026-10-13.** The GPU stack under its own compose project, gemma 12B as the cortex, the CPU
`llama-embed`, pgvector, Redis and `mcp-filesystem`, with `CORTEX_MEMORY_SCOPE` and
`CORTEX_TOOLS_ON_UNAVAILABLE` at their defaults (`global`, `fail`) and
`CORTEX_MEMORY_RECALL_AUDIT=1`. The real Linux shell ran on `Xvfb` as the
[overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless) describes, driven by
`xdotool`, with frames grabbed by `ffmpeg`. Some turns went over `Converse` from the host instead,
recording every event with its time from the turn's start. A container was stopped with
`docker stop`, killed with `docker kill`, frozen with `docker pause` and brought back with `docker
start` or `docker unpause`. Rows were read with `psql` on the `memories` table.

## Postgres

- **Restarted between turns** (`docker restart`, back in about a second): the next turn, in a new
  chat, recalled the earlier one ("When is my sister Ilona's birthday?" answered 14 March) with no
  warning in the brain log, and its exchange was stored. The pool replaced its closed connections
  on its own.
- **Restarted during a turn**, four seconds into a 150 word reply: the recall had already run, the
  write at the end was stored, and the person saw nothing unusual.
- **Stopped during a turn.** The overlay showed the status line "memory is unavailable, so this
  turn is answered without earlier notes" under the question, then the reply, and the line went
  away. The brain logged `memory recall unavailable; answering this turn without its recalled
  notes` and, after the reply, `memory write unavailable; this exchange was not recorded to
  memory`, both with `MemoryStoreError` over a `socket.gaierror` for the stopped host. The fact the
  person gave in that turn ("Ilona just moved to Pecs") was not stored, and nothing on screen said
  so, as decision 12 of [ADR-0008](../adr/ADR-0008-memory-v1.md) decides. Started again (healthy
  after 6 s), the next turn recalled the birthday and said it had nothing on where she lives.
- **Frozen during a turn** (`docker pause`), before the bound below: a turn over `Converse` showed
  no status at all for the 100 s the client waited, and the brain logged nothing. A second turn,
  from the shell, needed a new connection: it showed only the pending bubble until asyncpg's
  default 60 s connect timeout, then the status line above, then a reply.
- **No row was stored twice.** After every Postgres and sidecar flow on this page, the 12 rows in
  `memories` held 12 distinct texts.

## The bound on the store

`PgVectorMemoryStore` bounds each statement, and the orchestrator sets the bound to 10 s, about
seven times the slowest search [measured](model-lineup.md#memory-search), the exact scan over
220,000 memories. Neither asyncpg's `command_timeout` nor `asyncio.timeout` around a statement
bounded a turn: a probe in the brain's container showed the timed out statement's task staying
`cancelling` inside `PoolConnectionHolder.release` (asyncpg's `pool.py`, under `asyncio.shield`),
which waits for `Connection._cancel` to send a cancel request that the frozen server never
answers. So the store runs each statement as its own task, and past the bound cancels it without
waiting for it.

With that build and Postgres frozen after a warm turn, the status line came at 10.0 s, the reply
streamed, the write failed 10 s after the last text and the turn completed at 26.0 s. A second turn
during the freeze behaved the same. Unfrozen, the next turn recalled with no error in the log, and
no `Task exception was never retrieved` line appeared. SM clock 0.62 of `clocks.max.sm` after the
run.

## The embedding server

- **Killed between turns.** The status line showed 1.1 s into the turn, the reply came, and both
  the recall and the write logged `EmbedderError` over `httpx.ConnectError`. The exchange was not
  stored.
- **Started again**, a turn sent at once got `503 Service Unavailable` while the model loaded, so
  that turn too was answered without notes; the server listened about 2 s after the start and its
  write at the end of the turn was stored. The container reported healthy after 6 s.
- **Killed during a turn**, four seconds into a 150 word reply: the recall had run, the write
  failed, and the person saw nothing.
- **Frozen during a turn** (`docker pause`): the first event the turn sent was a heartbeat with no
  wait at 30.0 s, then the status line, when the 30 s embedder timeout ended the recall. The reply
  then streamed, and the turn completed 10.0 s after its last text, at 44.3 s, when the write's
  bound below ended it; the brain logged `memory write unavailable` over a `TimeoutError`. Unpaused,
  the next turn completed 0.1 s after its last text and its exchange was stored. SM clock 0.59 of
  `clocks.max.sm` after the run.

## The bound on the write

`record_exchange` bounds the whole write, the embedding and the insert, at
`MEMORY_WRITE_TIMEOUT_S` (10 s). Without it the write waited the embedder's whole 30 s timeout
after the reply was on screen, with the composer still showing the stop button, and the turn above
completed at 67.6 s. The bound rests on the time to embed one exchange, an input of 1,800
characters, the most `embedding_input` passes: 20 requests to the CPU `llama-embed` from the host,
first on an idle machine and then with twice as many busy loops as cores. Busy, the median took 11
times the idle median and the slowest 13 times; the bound is 36 times the idle median and 2.8 times
the slowest busy request. Method: 20 timed POSTs of one 1,800 character text to `/v1/embeddings`
on port 8081 from the host, the load from `yes` processes.

## The filesystem sidecar

- **Killed between turns**, under the default `CORTEX_TOOLS_ON_UNAVAILABLE=fail`: every turn failed
  before inference, including "What key is the Bach cello suite number six in?", which needs no
  file. The overlay showed the error bubble `internal: MCP sidecar unavailable` beside a green link
  dot, and the brain logged `unexpected failure handling a turn` over a `ToolError` raised by the
  tool listing at the start of the turn. The [tools runbook](../runbooks/tools-mcp.md) said the
  model sees an `is_error` result instead. Filed as
  [R-850](../refinements/tasks/850-one-down-sidecar-fails-every-turn.md).
- **Killed during a `read_text_file` call.** The sidecar was frozen after the model's
  `list_directory` call and killed 8 s later. The overlay showed "waiting for a tool to finish"
  under the `read_text_file` row for those 8 s; the call ended at the kill with `ok=False error="MCP
  sidecar unavailable"` in the tool audit, the model called `read_file` once more (failed at once),
  and replied that "the file `choir-rota.txt` appears to be unavailable or inaccessible as the
  content returned is "MCP sidecar unavailable"". The reply blames the file and quotes the error.
- **Started again**: the container reports `Up` while it is still running `npm install`, and it
  listened 3 to 6 s later. A turn in that window failed with the same error bubble; the next one
  read the file and answered.

Method: `docker logs` of the brain and the sidecar, `psql` on `memories`, `Converse` from the host
and the shell driven with `xdotool`; the drivers lived in the run's scratch directory.
