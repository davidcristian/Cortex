# A secret-named argument prints its value on both audit trails

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-17

The formatter withholds a field whose name matches `SECRET_NAMES`
(`cortex_core/log_fields.py`, `record_fields`), but it reads only the record's top-level field
names. The tool audit line attaches the call's arguments as one field, `arguments`, so a key
inside it is never read. Run on 2026-09-17 through `PlainFormatter`, a call with arguments
`{"password": "hunter2", "api_token": "abc"}` printed
`arguments={"api_token":"abc","password":"hunter2"}`, and `JsonLinesAuditSink` kept the same object,
because the file keeps exactly what the line prints.

No shipped tool takes a secret-named argument today: the filesystem sidecar's tools take paths and
contents, and the email tools take addresses, subjects and bodies. A model can still name any key
it likes in a call to a tool that ignores it, and a future sidecar may take a credential.

**What would be built.** Withhold a secret-named key's value at any depth inside a structured field,
in `render_value`, so the line and the file change together; `durable_value` in
`cortex_tools/audit_file.py` then keeps the formatter's rendering whenever the two differ, which
it already does. Pin it with a line test in `core/tests/test_log_format.py` and a file test in
`tools/tests/test_audit_file.py`. Withholding it in the file alone was rejected, because the two
trails would then disagree about one call. The code is in `brain/packages/core/`, which was
reserved for a running measurement on the day this was filed.

## Trail

- 2026-09-17: filed by the close of
  [353](353-a-trail-worth-querying-has-no-store.md), whose file sink reproduces the line's
  defences and so reproduces this gap. Recorded in the ADR-0009 durable-trail addendum.
