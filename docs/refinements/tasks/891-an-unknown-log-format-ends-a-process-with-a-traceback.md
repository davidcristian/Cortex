# An unknown log format ends a process with a traceback

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)
**Verified:** 2026-10-17

A refused setting ends the brain and the model host with one `setting refused` line naming its
variable, but the log rendering is checked outside that path. `CORTEX_LOG_FORMAT` and
`CORTEX_MODELHOST_LOG_FORMAT` are plain `str` fields that only `cortex_core.build_formatter`
checks: the brain's `configure_from_env` runs before the `try` in `entry.main`, and the model host
calls `configure_logging` after its settings are read. An unknown name ends either process with a
traceback whose last line is `UnknownLogFormatError: unknown log format '<value>'; this build
renders ['packed', 'plain']`, naming the value, which is harmless here, and not the variable.

## What to do

1. Refuse an unknown rendering while the settings are read, for example with a validator on both
   classes raising a `ConfigError` subclass, so `read_settings` reports it like any other value.
2. Write that refusal in the default rendering, since the value naming the rendering is the one
   refused, and exit 1.
3. Test both entry points with an unknown name, asserting one line that names the variable.

## History

- 2026-10-17: filed by the close of
  [R-890](890-a-sidecar-names-a-malformed-setting-by-its-field.md), which moved the sidecars onto
  the shared settings reader and found this path outside it. Run from the working tree with an
  unknown name, both processes exit 1 with a traceback of 14 to 16 lines ending as above.
