# The couplings the widened registry cannot cover

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)
**Verified:** 2026-09-19
**Trigger:** A third value on the capture-target enum, a reader for declarations in the `.proto`
arriving in the scan for another reason, any module outside the body's rpc crate and the brain's
body client that has to name one of the two gRPC status codes, or either side of that pair gaining
a declaration whose value the scan can read.

Once [R-012](012-couplings-crosscheck-omits.md) widened the registry to four kinds of coupling,
each remaining one became a decision. Five were recorded here over time and three have closed. Two
remain.

**A gRPC status code, written once per language's own casing.** The body writes
`Status::resource_exhausted` and `Status::failed_precondition`; the brain's classifier keys on
`grpc.StatusCode.RESOURCE_EXHAUSTED` and `FAILED_PRECONDITION`. The two sides must agree or a
refused capture is reported as a fault. Neither side declares a value the other could read:
tonic's form is a method name and grpc-python's is an enum member. What holds the pair today is
prose in both module docs plus a test table on each side, which is what the registry exists to
replace. A case-folding mention form (`Form.LOWERED`) arrived on 2026-09-15 for another
reason, and it does not help here: a case fold applies to a value a place declares, and neither
side declares one.

**A vocabulary generated on both sides.** `proto/body.proto` declares `CaptureTarget` with
`CAPTURE_TARGET_DISPLAY` and `CAPTURE_TARGET_FOCUS`; `body_core` and `cortex_core` each mirror it
as a hand-written enum; and the strings the model chooses between in `capture_screen`'s JSON
schema are a third copy. That third copy is already covered without the scan, because the schema
list is derived from `cortex_core.CaptureTarget`'s member values (`_TARGET_NAMES` in
`screen_tool.py`). What no scan covers is the two hand-written enums against the proto's. This is
the only coupling here with generated code on both sides, which is why it is out of reach rather
than merely awkward: `crosscheck.py` reads declarations out of source, and a protobuf enum becomes
a serialized descriptor in one tree and a derived Rust enum in the other, with no literal for a
template to match. Registering it means reading declarations out of the `.proto`, a parser this
repo does not have; the file itself is already a place the scan searches for rendered text. What
holds it today is the Rust compiler, a `match` over `PbCaptureTarget` being exhaustive so a new
proto value fails the build, and nothing at all on the Python side.

The three that closed:

- **A membership**, `CAPTURE_MIME` (`"image/png"`) inside the brain's `ALLOWED_MIME_TYPES`. Closed
  2026-08-11 as `Relation.MEMBER` plus a `frozenset` value form: every place but the last declares
  a value, the last declares the collection that must contain them, and the collection is reduced
  to its members so that the writer's order and spacing decide nothing. Shown able to fail in both
  directions, and the scan as it stood the previous commit exits 0 over one of them while
  reporting all fifteen constants agree. One limit stays by policy: a collection written in Rust
  or TypeScript does not reduce, and the reducer refuses what it cannot reduce rather than
  guessing. The close cost a file, both the scan and the registry being within twenty lines of
  300: the value forms and comparators moved to `scripts/values.py` (later split again into
  `scripts/readings.py`) and the overlay's half of the registry to `scripts/overlaycouplings.py`.
  The registry is now several parts, listed in `scripts/registry.py`'s docstring (fourteen on
  2026-09-19), and nothing in the scan asks which part an entry is in.
- **A custom property's use, where the TypeScript declares the value and not the name.** A mention
  renders a value, so it reaches `--roll: 300ms` on `:root` but not the two `var(--roll)` that
  read it, and the same was true of `--ease`. Closed 2026-08-11 by `Mention.name`, which renders
  the name a far side reads the value under, so the pair is two mentions of one entry:
  `{name}: {value}ms;` over the declaration and `var({name})` over the uses. The alternative, a
  name constant in `overlay/morph.ts` that nothing imports, was rejected as a declaration written
  only to be read by a check. `var(--roll)` is fixed at 2 occurrences, those two rules being a set
  that moves together; `var(--ease)` is a presence check, since the transitions using that curve
  span unrelated features and numbered 52 that day and 49 later, so a count would fail on every
  unrelated change. What it does not reach, recorded rather than left to be found: a mistyped use
  of a presence-checked property is still undetected, and closing that needs a stylesheet-wide
  check that every `var()` names a property something declares.
- **The body's bind port 50151**, a bare literal in `body/app/src-tauri/src/body_server.rs`
  against `docker-compose.body.yml`. Its argument was that a constant there would be a source edit
  nothing type-checks, and its trigger was the shell entering CI, which happened on 2026-08-17
  ([R-009](009-shell-clippy-in-ci.md)). Struck 2026-09-06, though it had in fact been registered
  since 2026-08-22 by [R-356](356-the-body-port-is-a-bare-literal.md) and widened to 23 far sides
  the next day by [R-383](383-the-body-port-past-the-six-that-were-registered.md), so the coupling
  was covered and listed here as uncovered at the same time. The remedy was filed as
  [R-593](593-the-bodys-bind-port-can-be-declared-now-the-shell-compiles.md) and closed satisfied
  on 2026-09-07. What survives of the argument is
  [R-595](595-no-gate-compiles-the-tauri-shells-windows-half.md): a declaration inside the Tauri
  shell is read by the scan on every `just check` and compiled by nothing, both clippy runs over
  that crate targeting the Linux host while the constant is `cfg(windows)`.

A fourth, the roll duration written as `0.3s` in the stylesheet against `MORPH_ROLL_MS` in
milliseconds, closed on 2026-08-09 when `:root` gained `--roll: 300ms` and the two rules that move
with a roll read it. Its own arithmetic was wrong first: the sheet wrote `0.3s` seven times, not
thirty, six declarations and one comment. The four declarations that keep a literal do so
deliberately, being the panel's summon fade and three arrivals, which a retune of the roll must
not also retune.

## History

- 2026-08-08: Opened behind the widened registry, as three couplings. A fourth, the gRPC status
  code, joined the same day and is recorded here rather than counted beside it.
- 2026-08-09: Still four. The roll duration closed onto a `--roll: 300ms` custom property, with
  its own arithmetic corrected first, and the question of reading a property's uses opened in its
  place.
- 2026-08-09: All four were checked against the tree and none had moved. `CAPTURE_MIME` was still
  the single encoding `"image/png"`, the bind port still had its only declaration inside the crate
  nothing compiled, and `scripts/couplings.py` still registered exactly two value-declaring
  properties.
- 2026-08-10: Five, by arrival: the capture target's proto enum against the schema strings the
  model chooses between, the first coupling here with generated code on both sides.
- 2026-08-11: Four, when the membership closed as `Relation.MEMBER` plus a `frozenset` value form,
  taking the registry to sixteen entries and costing two file splits.
- 2026-08-11: Three later the same day, when the custom property's use closed on `Mention.name`,
  leaving behind one presence-checked name.
- 2026-09-06: The shell clause fired, the Tauri shell having entered CI on 2026-08-17, so the
  bind port's remedy became ordinary work and was filed on its own.
- 2026-09-06: The other two clauses were counted and neither had fired. The capture target still
  had exactly two values, and the status pair was still written in two trees and nowhere else.
- 2026-09-06: The status pair's trigger, "a third status-table caller", was not decidable as
  written, since a caller could mean a third code, a third call site or a third module. It is
  restated to the module reading, since a second call site inside one file agrees with itself.
- 2026-09-07: The bind port had in fact been satisfied since 2026-08-22 rather than on the day it
  was struck, and its remedy closed satisfied.
- 2026-09-09: Both remaining couplings read again and neither trigger fired.
- 2026-09-09: Three accounts of closed sub-entries had gone stale: the number of registry parts,
  the split of `values.py`, and the count of `var(--ease)` uses, which is 49 today.
- 2026-09-14: Both couplings checked again and neither trigger fired. The status codes are written
  in three non-test modules, all inside the two places this entry names.
- 2026-09-15: Both checked again. The registry's own widenings were read against them, which had
  not been done before: `crosscheck.DECLARATIONS` still knows `.py`, `.rs` and `.ts` only, so no
  `.proto` reader has arrived, and the case-folding mention form that did arrive reaches nothing
  here.
- 2026-09-19: Both checked again after the settings scan and the nearest-line report, and neither
  trigger fired. Two things here had gone stale: the registry part count, fourteen since
  2026-09-13, and the trigger line, which named two of the four events the sub-entries wait on. It
  now names all four.
