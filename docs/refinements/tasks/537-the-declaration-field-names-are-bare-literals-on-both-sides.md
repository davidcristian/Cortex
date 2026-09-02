# The two field names a declared source is written under are bare literals on both sides

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-02 by the close of
[534](534-the-declared-kind-word-has-no-site-to-hold-it.md), which held the kind word a
declaration carries and found the two names it is written under unheld.

A sidecar's declaration is a mapping with two fields. `_sender_source` in `cortex_email/server.py`
writes it as `{"kind": _SENDER_KIND, "value": sender}`, and `_declared_source` in
`cortex_tools/registry.py` reads it as `fields.get("kind")` and `fields.get("value")`. The two
field names are spelled as bare literals at both ends, in two packages that cannot import each
other, and nothing under `scripts/` names either. A field renamed on one side alone hands
`claimed_source` a `None` in that position, and `claimed_source` returns `None` for a non-string
kind or value, so every `read_email` would arrive without its sender and nothing would fail: the
third pair on this wire to carry that silence, after the key and the kind word.

**What would close it.** The key's pattern, twice: bind each name on each side, `_KIND_FIELD` and
`_VALUE_FIELD` in both modules, and register two entries in `scripts/emailcouplings.py` with the
two bindings as sites and each module's spend of its own binding as a mention. Then the mutation:
re-spell one side's binding alone and watch `check-crosscheck` fail naming both files. Both suites
already pin the literals (`test_email_server.py`, `test_registry.py`), and those pins stay
unregistered for the reason the key's addendum gives.

## Trail

- 2026-09-02: opened by the close of
  [534](534-the-declared-kind-word-has-no-site-to-hold-it.md).
