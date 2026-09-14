# A startup traceback reaches stderr with no formatter

**Status:** open, fix when it bites
**Area:** brain
**Trigger:** a startup failure whose exception text carries something the log formatter would
withhold, most plausibly a connection URL with a credential inside it. Two readings answer it:
`grep -rn "asyncio.run" brain/packages/orchestrator/src` says whether anything guards the entry
point, and raising from inside `run_from_env` says what the container's last line looks like. This
entry's trail records what both answered when they were last taken.
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-14

Opened 2026-09-14 by the landing of
[R-652](652-a-credential-can-leave-the-process-with-no-url-around-it.md), which refused one
unreadable DSN at the boot that reads it and left this half of that entry standing.

`__main__.py` runs `asyncio.run(run_from_env())` under a bare entry guard with no `except` around
it, and `run_from_env` builds every adapter, several of which dial a remote with a credential in
the URL. An exception from any of them is printed by the interpreter's own traceback hook to
stderr. `logging` never sees it, so neither `PlainFormatter` nor the whole-line withholding runs,
and the container log carries whatever the exception said, its `__cause__` chain included.

The shape available is a guard around `asyncio.run` that logs the exception through the configured
handler and exits non-zero, which routes every startup traceback through the formatter. Two things
are unsettled. It changes what a crashed container's last line looks like, from a Python traceback
an operator reads by eye to one rendered line plus whatever the formatter does with the traceback
text. And the entry guard is `# pragma: no cover`, so the guard itself would need the coverage
escape too, or `run_from_env` would need to grow the handling one level in where the suite reaches
it, which
puts a process-exit decision inside the composition root.

What the guard does not cover is what made the DSN refusal a separate change: the formatter
withholds a credential by URL shape, and a failure whose text carries a fragment of a password
with no scheme and no `@` around it passes through every pattern this repo owns. Routing more
failures through the formatter widens what is withheld; it does not make the formatter able to
recognise a bare fragment.

## Trail

- 2026-09-14: opened by the landing of
  [R-652](652-a-credential-can-leave-the-process-with-no-url-around-it.md). `__main__.py` runs
  `asyncio.run(run_from_env())` under an entry guard carrying `# pragma: no cover`, with no
  `except` anywhere in the file, and `memory_builders.py` awaits `PgVectorMemoryStore.connect`
  with no `except` around it either, so a memory backend that cannot be dialed still ends the
  process through the interpreter's hook.
