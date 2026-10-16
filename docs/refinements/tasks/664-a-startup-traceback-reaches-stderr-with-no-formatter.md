# A startup traceback reaches stderr with no formatter

**Status:** open, waiting for its trigger
**Area:** brain
**Trigger:** a startup failure whose exception text contains something the log formatter would
withhold, most plausibly a connection URL with a credential inside it. Two readings answer it:
`grep -rn "asyncio.run" brain/packages/orchestrator/src` says whether anything guards the entry
point, and raising from inside `run_from_env` says what the container's last line looks like. This
entry's history records what both answered when they were last taken.
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)
**Verified:** 2026-10-16

`entry.main` runs `asyncio.run(run_from_env())` and catches only `ConfigError`, a refused setting,
which it logs as one line before exiting 1. `run_from_env` builds every adapter, several of which
dial a remote with a credential in the URL. An exception from any of them is printed by the interpreter's own traceback hook to stderr.
`logging` never sees it, so neither `PlainFormatter` nor the whole-line withholding runs, and the
container log keeps whatever the exception said, its `__cause__` chain included.

The available fix widens the `except` in `entry.main` to every exception, logging it with its
traceback through the configured handler and exiting non-zero, which routes every startup traceback
through the formatter. `entry.main` is covered by tests, so the guard needs no coverage escape. What
is unsettled is that it changes what a crashed container's last line looks like, from a Python
traceback an operator reads by eye to one rendered line plus whatever the formatter does with the
traceback text.

What the guard does not cover is what made the DSN refusal a separate change: the formatter
withholds a credential by URL shape, and a failure whose text has a fragment of a password with no
scheme and no `@` around it passes through every pattern this repo owns.

## History

- 2026-09-14: opened by the close of
  [R-652](652-a-credential-can-leave-the-process-with-no-url-around-it.md), which refused one
  unreadable DSN at the boot that reads it and left this half. `__main__.py` runs
  `asyncio.run(run_from_env())` under an entry guard with `# pragma: no cover` and no `except`
  anywhere in the file, and `memory_builders.py` awaits `PgVectorMemoryStore.connect` with no
  `except` around it either, so a memory backend that cannot be dialed ends the process through the
  interpreter's hook.
-  2026-09-19: both readings taken, and the trigger has not fired. The grep finds one `asyncio.run`,
  at `cortex_orchestrator/__main__.py` line 18, still unguarded. The second reading ran the
  orchestrator from the working tree (`brain/.venv/bin/python -m cortex_orchestrator`) with a
  password fragment in each credential-bearing URL. With `CORTEX_REDIS_URL` pointing at a port
  nothing answers, the process logged `seam server listening` and served, because the Redis stores
  dial lazily, so that URL cannot end the boot at all. With `CORTEX_MEMORY_BACKEND=pgvector` and a
  DSN whose host does not resolve, the boot ended with exit 1 through the interpreter's hook: a raw
  traceback on stderr, last line `socket.gaierror: [Errno -2] Name or service not known`, and the
  fragment appeared nowhere in stderr or stdout, chained exceptions included. A port that could not
  be bound ended the same way, with a `RuntimeError` naming only the bind address. So the path this
  entry describes is real and still unformatted, but neither dial with a credential in it puts that
  credential into the exception text today.
- 2026-09-30: both readings taken again, and the trigger has not fired. The grep finds one
  `asyncio.run`, now at `cortex_orchestrator/__main__.py` line 12, still under the bare entry guard,
  and `build_memory` still awaits `PgVectorMemoryStore.connect` with no `except` in
  `memory_builders.py`. Run from the working tree with `CORTEX_MEMORY_BACKEND=pgvector` and a DSN
  whose host does not resolve and whose password is a marked fragment, the boot again ended with exit
  1 and a raw 66-line traceback ending in `socket.gaierror`, and the fragment appeared in neither
  stream.
- 2026-10-04: both readings taken again, and the trigger has not fired. The grep finds the one
  `asyncio.run` at `cortex_orchestrator/__main__.py` line 12, still under the bare entry guard, and
  nothing on the startup path has changed since 2026-09-30. The same pgvector boot with an
  unresolvable host and a marked password fragment ended with exit 1 and a raw 66-line traceback
  ending in `socket.gaierror`, and the fragment appeared in neither stream.
- 2026-10-13: Not fired. The grep finds the one `asyncio.run` at
  `cortex_orchestrator/__main__.py:12`, still under the bare entry guard. Since 2026-10-10 the boot
  awaits one more remote call, the serving watch's first reading (`wiring.py:126`,
  `serving_watch.py:77`), and both of its probes turn a failure into a fault line rather than an
  exception: the Redis `PING` on `RedisError` (`cortex_session/ping.py:25`) and the cortex's health
  request on `httpx.HTTPError` (`serving_probe.py:73`). So a Redis URL nothing answers still cannot
  end the boot.
- 2026-10-16: Not fired. The one `asyncio.run` moved to `cortex_orchestrator/entry.py` `main`,
  which now catches `ConfigError` and logs a refused setting as one `setting refused` line with
  exit 1. Every other exception still reaches the interpreter's hook, so this entry's question is
  unchanged.
