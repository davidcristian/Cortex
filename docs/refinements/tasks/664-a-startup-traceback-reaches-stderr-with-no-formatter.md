# A startup traceback reaches stderr with no formatter

**Status:** open, waiting for its trigger
**Area:** brain
**Trigger:** a startup failure whose exception text contains something the log formatter would
withhold, most plausibly a connection URL with a credential inside it. Two readings answer it:
`grep -rn "asyncio.run" brain/packages/orchestrator/src` says whether anything guards the entry
point, and raising from inside `run_from_env` says what the container's last line looks like. This
entry's history records what both answered when they were last taken.
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)
**Verified:** 2026-09-19

`__main__.py` runs `asyncio.run(run_from_env())` under a bare entry guard with no `except` around
it, and `run_from_env` builds every adapter, several of which dial a remote with a credential in the
URL. An exception from any of them is printed by the interpreter's own traceback hook to stderr.
`logging` never sees it, so neither `PlainFormatter` nor the whole-line withholding runs, and the
container log keeps whatever the exception said, its `__cause__` chain included.

The available fix is a guard around `asyncio.run` that logs the exception through the configured
handler and exits non-zero, which routes every startup traceback through the formatter. Two things
are unsettled. It changes what a crashed container's last line looks like, from a Python traceback
an operator reads by eye to one rendered line plus whatever the formatter does with the traceback
text. And the entry guard is `# pragma: no cover`, so the guard itself would need the coverage
escape too, or `run_from_env` would have to grow the handling one level in, which puts a
process-exit decision inside the composition root.

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
