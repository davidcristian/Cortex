# The trail's logger name is written in three places and checked nowhere

**Status:** done 2026-08-28
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`cortex.memory.recall` is written in `brain/packages/memory/src/cortex_memory/audit.py` as the
argument of the `logging.getLogger` call, and restated in two documents:
[memory-pgvector.md](../../runbooks/memory-pgvector.md) says the trail is one `cortex.memory.recall`
line per recall, and [local-dev-wsl.md](../../runbooks/local-dev-wsl.md) names it among the loggers
a deployment can raise or lower. Rename it and both sentences instruct an operator about a logger
nothing writes through, with every check passing.

The registry compares a declaration with the places restating it, and there was no declaration
here: the name is a call argument, so registering it means adding a module-private constant to the
sink.

## History

- 2026-08-27: opened by the close of
  [R-454](454-the-readers-needles-are-not-tied-to-the-sink.md), whose search text for the message is
  written as the emitting call so that it cannot be satisfied by this name.
- 2026-08-28: closed, as
  [ADR-0045 decision 13](../../adr/ADR-0045-documented-log-lines.md) and an entry in
  `scripts/trailcouplings.py`, a new registry part: the logger took `logcouplings.py` past the line
  cap, so the recall trail's three words moved into a part of their own. The sink declares
  `_LOGGER_NAME` and the two runbooks and the module contract are the places compared with it. Both
  halves of this entry's account were stale. The reopen condition named a third document telling an
  operator to select the trail by logger name, and `docs/modules/brain-memory.md` had been that
  document since the trail was added, three weeks before the entry was written. And a rename was
  never clean everywhere: nine of the memory package's forty tests read a line back through
  `caplog` under this name, so a rename fails in the tree that writes the trail and goes unreported
  in the three documents that read it, which is what makes leaving the documents behind plausible.
  The `samplecheck.py` alternative was measured and declined, because finding a logger name in a
  document by its shape also finds `cortex.seam.v1` and `cortex.dump`, and reaching the
  module-path loggers two runbooks name would reach every module reference in every module
  contract. `scripts/logcalls.py` gained the third form of a logger claim in the same slice, so the
  trail stays in the sample check's answer now that it has a declaration. Opened by this close:
  [R-486](486-the-tool-audits-logger-name-is-spelled-in-four-places-and-held-in-none.md).
