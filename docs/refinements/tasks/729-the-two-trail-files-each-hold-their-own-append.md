# The two trail files each hold their own append

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-10-03
**Trigger:** either sink's open, append or gap warning changes, or the two copies stop matching. On
2026-10-03, `git log -1 --format=%ad --date=short -- '*/src/*/audit_file.py'`, which names the two
sinks' files, prints 2026-09-25, the commit that filed this task, and the 13 lines from
`descriptor = os.open` to `os.close(descriptor)` plus `_append` are identical in the two files.

`JsonLinesAuditSink` (`brain/packages/tools/src/cortex_tools/audit_file.py`) and
`JsonLinesRecallSink` (`brain/packages/memory/src/cortex_memory/audit_file.py`) each open the file
per record with `O_APPEND` and mode `0600`, each hold an `_append` that starts a record on a new
line after a torn one, and each log a gap warning on a refused open or write. The value rules they
share moved into `cortex_core/log_durable.py`, but the append is file I/O, which the core may not
import, and no adapter package is imported by both `cortex_tools` and `cortex_memory`: each depends
on `cortex-core` and its own client library only. So the same 13 lines exist twice, and a fix made
in one sink can be missed in the other.

What each sink catches differs on purpose. The tool sink also turns a renderer failure (`TypeError`,
`ValueError`, `RecursionError`) into a gap, because its records hold model-written arguments; the
recall sink catches `OSError` alone, since its fields are ids, counts, scores and flags the brain
writes, and `durable_value` already turns a non-finite score into text. A shared helper takes the
open and the append and leaves each sink its own catch.

**What would be built.** A small adapter package, for example `cortex_trail`, holding one
`append_record(path, data)` that both sinks call, added as a workspace member with its own contract
doc. It is deferred because adding a workspace member changes `uv.lock` and the synced environment,
and the two copies of the open and the append agree today: each is covered by its own sink's tests
for the mode, the torn line, a moved file and a refused append.

## History

- 2026-09-25: filed by the close of
  [683](683-the-recall-trail-has-no-store.md), which added the second copy.
- 2026-10-03: Not fired. Neither sink has changed since the commit that filed this task, and the
  open and the append still match line for line. Two corrections: the duplicated code is 13 lines,
  not fifteen, and the two sinks differ in what a failed record catches, by design, so the shared
  helper the entry proposes covers the open and the append and not the catch. The trigger now names
  the command and the comparison that decide it.
