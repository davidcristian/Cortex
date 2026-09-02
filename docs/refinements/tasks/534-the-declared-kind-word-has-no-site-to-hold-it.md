# The kind word a declared source rides under is spelled twice and has no declaring site

**Status:** landed 2026-09-02
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-02 by the close of [531](531-the-source-declaration-key-is-spelled-twice-unheld.md),
which held the `_meta` key `read_email` declares a sender under equal at both of its bindings and
found the word beside it unheld. `_sender_source` in `cortex_email/server.py` writes
`{"kind": "sender", "value": <From>}` with `sender` as a bare literal, and the brain admits a
declaration through `claimed_source` only when its kind is a key of `_DECLARABLE_KINDS`
(`cortex_core/provenance.py`), which is built from `SourceKind`'s own members, so the brain's one
spelling of the word is the enum member `SENDER = "sender"`. That member is indented inside the
class, and the Python declaration syntax in `crosscheck.DECLARATIONS` is anchored at column 0 so a
name bound inside a function is never read as a second declaration of a module's constant; an enum
member is therefore not a `Site`, and a `Constant` with no site is refused by the registry as
establishing nothing. A renamed enum value alone would have `claimed_source` return `None` for
every message read, the same silence the key's entry named, with the sidecar still writing the
old word. The `URI` twin rides the same channel and has no producer yet.

**What would close it.** One of two roads, decided and recorded at the origin ADR. The narrow one
is a module-level binding in the server, `_SENDER_KIND = "sender"`, as the `Site`, spent where
`_sender_source` builds the declaration, with a `Mention` on `provenance.py` rendering
`SENDER = "{value}"`; it costs one binding and holds the word today. The wide one teaches the
Python declaration syntax an indented class-level form, which makes every enum in the brain
registrable and has to tell a class body from a function body, a distinction the column-0 anchor
was chosen so the scan would never have to draw. Either way, the mutation: rename the enum value
alone and watch `check-crosscheck` fail naming both files.

## Trail

- 2026-09-02: opened by the close of
  [531](531-the-source-declaration-key-is-spelled-twice-unheld.md).
- 2026-09-02: landed by the narrow road, recorded in the ADR-0029 declared-kind-word addendum.
  Every claim above held on re-derivation. `cortex_email/server.py` binds the word as
  `_SENDER_KIND` and spends it in `_sender_source`; one entry in `scripts/emailcouplings.py` has
  that binding as its site and, as mentions, the enum member rendered name and value, the server's
  spend and the module contract's quotation, and the live gate fails on a rename of either side
  alone. The wide road is filed as
  [536](536-the-python-declaration-syntax-reads-no-class-level-binding.md), the declaration's two
  field names as [537](537-the-declaration-field-names-are-bare-literals-on-both-sides.md), and
  the unfound-needle hedge over an ordinary word as
  [538](538-an-unfound-needle-over-an-ordinary-word-reads-prose-as-the-value.md).
