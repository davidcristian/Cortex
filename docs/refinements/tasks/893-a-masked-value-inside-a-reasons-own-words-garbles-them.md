# A masked value inside a reason's own words garbles them

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)
**Verified:** 2026-10-17

`read_settings` (`cortex_settings/read.py`) replaces every occurrence of a refused value in a
validator's message with `<value>`, so the value is never shown. When the value also occurs inside
the message's fixed text, those occurrences are replaced too. `CORTEX_LOG_FORMAT=pack` ends the
brain with `CORTEX_LOG_FORMAT: unknown log format '<value>'; this build renders ['<value>ed',
'plain']`, which hides the name the operator most likely meant. A one-letter value replaces every
copy of that letter.

## What to do

1. Mask only the occurrences the validator wrote from the input, for example by replacing the
   value's `repr` when the message quotes it, while keeping any other copy masked when the value
   could be a secret.
2. Test a value that is a prefix of a word in the message, and a secret-named field, asserting the
   fixed text whole and the value absent.

## History

- 2026-10-17: filed by the close of
  [R-890](890-a-sidecar-names-a-malformed-setting-by-its-field.md), from the run above.
