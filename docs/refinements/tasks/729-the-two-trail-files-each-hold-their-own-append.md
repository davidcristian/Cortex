# The two trail files each hold their own append

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-25
**Trigger:** A change to how either trail file opens, frames or reports a failed append, such as a
new file mode, an `fsync`, or a gap line with another field.

`JsonLinesAuditSink` (`brain/packages/tools/src/cortex_tools/audit_file.py`) and
`JsonLinesRecallSink` (`brain/packages/memory/src/cortex_memory/audit_file.py`) each open the file
per record with `O_APPEND` and mode `0600`, each hold an `_append` that starts a record on a new
line after a torn one, and each log a gap warning on a refused open or write. The value rules they
share moved into `cortex_core/log_durable.py`, but the append is file I/O, which the core may not
import, and no adapter package is imported by both `cortex_tools` and `cortex_memory`. So the same
fifteen lines exist twice, and a fix made in one sink can be missed in the other.

**What would be built.** A small adapter package, for example `cortex_trail`, holding one
`append_record(path, data)` that both sinks call, added as a workspace member with its own contract
doc. It is deferred because adding a workspace member changes `uv.lock` and the synced
environment, and the two copies agree today: each is covered by its own sink's tests for the mode,
the torn line, a moved file and a refused append.

## History

- 2026-09-25: filed by the close of
  [683](683-the-recall-trail-has-no-store.md), which added the second copy.
