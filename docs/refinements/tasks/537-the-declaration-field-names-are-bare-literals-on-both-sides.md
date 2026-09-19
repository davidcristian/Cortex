# The two field names in a source declaration are bare literals on both sides

**Status:** done 2026-09-02
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

A sidecar's declaration is a mapping with two fields. `_sender_source` in `cortex_email/server.py`
writes it as `{"kind": _SENDER_KIND, "value": sender}`, and `_declared_source` in
`cortex_tools/registry.py` reads it as `fields.get("kind")` and `fields.get("value")`. Both field
names were bare literals at both ends, in two packages that cannot import each other, and nothing
under `scripts/` compared them. A field renamed on one side alone hands `claimed_source` a `None` in
that position, and `claimed_source` returns `None` for a non-string kind or value, so every
`read_email` would arrive without its sender and nothing would fail.

## History

- 2026-09-02: opened by the close of [534](534-the-declared-kind-word-has-no-site-to-hold-it.md).
- 2026-09-02: fixed as proposed, recorded in ADR-0042. One premise was wrong: `scripts/` did contain
  the `kind` field, inside the kind-word entry's search text for the server, so a rename of that
  field on the server alone already failed the check under the wrong label. Both modules now bind
  `_KIND_FIELD` and `_VALUE_FIELD` beside the key and use them; two entries in
  `scripts/emailcouplings.py` compare each pair of bindings, each module's use of its own binding
  and both contracts' quotation, and the check fails naming both files when either side is renamed.
  Both test suites already assert the literals (`test_email_server.py`, `test_registry.py`) and stay
  unregistered for the reason the key's record gives. The cost shown by the fifth mutation, one
  entry's search text including another entry's binding name, is filed as
  [539](539-a-spend-beside-another-entrys-binding-carries-that-name-as-shape.md).
