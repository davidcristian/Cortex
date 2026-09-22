# The kind word in a source declaration is written twice and no check compares them

**Status:** done 2026-09-02
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`_sender_source` in `cortex_email/server.py` writes `{"kind": "sender", "value": <From>}` with
`sender` as a bare literal. The brain accepts a declaration only when its kind is a member of
`SourceKind` (`cortex_core/provenance.py`), so the brain's one copy of the word is the enum member
`SENDER = "sender"`. That member is indented inside the class, and the Python declaration pattern in
`crosscheck.DECLARATIONS` matches only a name at column 0, so an enum member cannot be a declaration
and a `Constant` with no declaration is refused by the registry. Renaming the enum value alone would
make `claimed_source` return `None` for every message read, with the sidecar still writing the old
word and nothing failing. The `URI` member goes over the same channel and has no producer yet.

Two ways to fix it, decided at the origin ADR. The narrow one binds `_SENDER_KIND = "sender"` at
module level in the server, uses it in `_sender_source`, and compares it against the enum member
from the registry: one binding, and the word is checked today. The wide one teaches the Python
declaration pattern to read a binding inside a class body, which makes every enum in the brain
registrable but has to tell a class body from a function body, the distinction the column-0 anchor
was chosen to avoid.

## History

- 2026-09-02: opened by the close of
  [531](531-the-source-declaration-key-is-written-in-two-trees-and-no-check.md).
- 2026-09-02: fixed the narrow way, recorded in ADR-0042. `cortex_email/server.py` binds
  `_SENDER_KIND` and uses it in `_sender_source`; one entry in `scripts/emailcouplings.py` compares
  that binding against the enum member, the server's use of it and the module contract's quotation,
  and the check fails naming both files when either side is renamed. The wide way is filed as
  [536](536-the-python-declaration-syntax-reads-no-class-level-binding.md), the declaration's two
  field names as [537](537-the-declaration-field-names-are-bare-literals-on-both-sides.md), and the
  misleading report over an ordinary word as
  [538](538-an-unfound-search-text-over-an-ordinary-word-reads-prose.md).
