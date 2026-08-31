# ADR-0003: Seam codegen and packaging (Slice 2)

- **Status:** Accepted
- **Date:** 2026-06-28

## Context

Slice 2 makes `proto/body.proto` real on both sides of the seam. That forces decisions
about stub generation, where generated code lives, how it stays exempt from the gates
(ADR-0001 d7, ADR-0002 d4), and which gRPC stacks to use.

## Decisions

1. **Generated stubs are committed**, only inside `_generated` directories:
   `body/crates/rpc/src/_generated/` and `brain/packages/seam/src/cortex_seam/_generated/`.
   Builds are hermetic, so CI and fresh clones never need protoc. Regeneration is a dev
   action: `just proto` (requires a local protoc; 35.1 at the time of writing). A regen
   diff is reviewed like any other change; the proto file's field numbers are frozen, so
   extend, don't renumber.
2. **Rust stack: tonic.** Regeneration is env-gated inside `build.rs`
   (`CORTEX_REGEN_PROTO=1`); a normal build does nothing. The generated file is
   `include!`d inside a wrapper module carrying the needed `allow` attributes
   (`cargo fmt` does not format `include!`d files). Coverage exemption is enforced by
   `--ignore-filename-regex '/_generated/'` on the `check-body` llvm-cov invocation.
3. **The Rust integration suite is `#[ignore]`-marked tests** (e.g.
   `crates/rpc/tests/live.rs`), the Rust analog of the Python `integration` marker
   (AGENTS gate 3): compiled but never run in CI or under coverage; run explicitly
   against a live brain via `just` recipes with `-- --ignored`.
4. **Python stack: grpcio + grpcio-tools** (mature `grpc.aio`), not betterproto.
   Committed `*_pb2.py` / `*_pb2_grpc.py` plus `.pyi` stubs so pyright strict works for
   consumers while `_generated` itself is excluded from ruff/pyright/coverage/linecap.
   Package-absolute imports are produced by staging the proto under
   `cortex_seam/_generated/` before invoking protoc.
5. **Python generated code lives in `brain/packages/seam` (`cortex_seam`).** It is shared
   wire code consumed by the orchestrator (server side) today and the future
   `body_client` (Slice 9, typed `BodyService` client wrapper). This deviates from the
   original layout sketch that placed stubs in `body_client`; ROADMAP updated.
6. **Seam config contract:** the brain server reads `CORTEX_SEAM_HOST` (default
   `127.0.0.1`; `0.0.0.0` inside the container) and `CORTEX_SEAM_PORT` (default
   `50051`) via pydantic-settings; the body-side live check reads `CORTEX_BRAIN_ADDR`
   (default `http://127.0.0.1:50051`). Compose publishes the port on loopback only
   (single-user security posture, ROADMAP assumption 5).

## Consequences

- Proto changes produce generated-code diffs in the same commit, which is noisy but reviewable,
  and it keeps every build reproducible without a protoc dependency.
- protoc/tonic-build/grpcio-tools version bumps can produce spurious regen diffs;
  regenerate deliberately, not as a side effect (the env gate exists for exactly this).
- Regenerating stubs ratchets the gencode-enforced runtime minimums (the generated code
  refuses to import under older grpcio/protobuf), so the declared floors in the
  seam/orchestrator `pyproject.toml`s must be bumped together with every regen.
- tonic-build compiles as a build-dependency on fresh builds (~tens of seconds, cached
  in CI by rust-cache) even though normal builds skip codegen.

## Addendum (2026-07-03): the Slice-2 retry/reconnect deferral, recorded here

Slice 2's one consciously deferred refinement is a transport retry / backoff / reconnect
policy behind the unchanged `BrainTransport` port (the thin `body_rpc` adapter does **no
retries**; a dropped stream or transient failure surfaces straight to the caller, and the
overlay treats a failed turn as terminal until the refinement lands) was recorded in the
ROADMAP deferred-refinements ledger and [body-rpc.md](../modules/body-rpc.md) but never at
this, its origin ADR. Added when the 2026-07-02 audit flagged the missing ADR-side half of
the AGENTS.md gate-4 record. **Landed 2026-07-08 as [ADR-0024](ADR-0024-transport-retry.md)**
with a `RetryingTransport` decorator + `Sleeper` port + lazy `connect_lazy_with_token` channel,
all behind the unchanged `BrainTransport` port. Jitter and a patient eager dial followed on
2026-07-13, and the per-method policy on 2026-07-16 (a `RetryPlan` gate that answers which
calls may be repeated at all, plus a bounded `Health` probe), each behind the same unchanged
port; see that ADR's addenda. What remains open from this deferral is `converse` resilience,
which is the one part no decorator over this port can deliver: reconnecting a turn before its
first event needs a replayable request and so a different signature.

## Addendum (2026-08-25): the committed stubs are held to the proto's comments, and to nothing else

Nothing compared the committed stubs with the proto they came from, so this measured what each
candidate check would catch before choosing one. The measurement favoured the cheap check: a text
comparison of comments catches the one kind of drift that produces no other error, while the
expensive regenerate-and-diff catches only drift that the compiler and pyright already report.

**Regenerating the Python stubs is free and reproduces exactly.** `grpcio-tools` is already a
brain dev dependency and ships its own `protoc`, so no new toolchain is involved. Regenerated
into a temporary directory and compared against the committed copies, all three files came out
byte identical (`body_pb2.py`, `body_pb2.pyi`, `body_pb2_grpc.py`). A regenerate-and-diff step
inside `check-brain` would therefore have worked, and it was still declined, for the next reason.

**It does not detect a changed comment.** Editing the proto comment that states the body's default
capture edge by a single digit and regenerating left all three Python files byte identical again.
The generated `.pyi` carries no comments at all, and `body_pb2.py` embeds a descriptor whose source
info is stripped. So the check would have covered structural drift only, and structural drift
already produces a visible error: a renamed or removed field fails pyright and fails the Rust
compile, and a field added to the proto that nobody regenerated for is a field nobody uses yet.

**The undetected case is real and it is in the Rust stub.** `prost` copies proto comments verbatim
into `body/crates/rpc/src/_generated/cortex.seam.v1.rs`, 338 doc-comment lines of them, and that
file is what a Rust reader opens. The comment stating the body's default edge is a registered far
side of a cross-language constant in `crosscheck.py`'s registry; its generated copy is not,
generated code being outside every scan here. So retuning the edge fails `crosscheck.py` against
the proto, and regenerating updates the stub, but skipping the regeneration leaves the stub stating
the old number in the file a reader opens, with no gate reporting it. Meanwhile the Rust half of a
regenerate-and-diff cannot join
`just check` at all, because `tonic-prost-build` needs a system `protoc` binary that a clean dev
box need not have, which is the toolchain the committed-stub decision above exists to avoid
requiring.

**Decision: `scripts/stubcheck.py` holds every comment the proto's body carries to the committed
Rust stub, as a text comparison running no codegen, and the regenerate-and-diff is declined.**
The comparison skips the file header above `syntax = `, which attaches to no declaration and which
`prost` does not copy, and normalizes three mechanical transformations `prost` applies on the way
out: it escapes `[` and `]` so rustdoc does not treat them as intra-doc links, it markdown-ifies a
service-level block so a line following a rule comes out with heading markers, and it collapses a
rule of any length. Measured against the tree as it stands, the proto's body carries 208 comment
lines, 177 leading and 31 trailing, and all 208 are present in the stub under exactly those three
normalizations and no others. The gate runs in every environment including CI, needs no `protoc`,
no docker and no GPU, and it is the second of the three answers in the ADR-0011 addendum on
evidence out of the gate's reach: a cheaper question the tree can already answer, chosen because
the measurement showed it catches strictly more of what matters than the expensive one does.

The gate's limits are stated here so nobody takes it for more than it is. It is not a regeneration
check. It does not detect a field added to the proto and missing from either stub, and it does not
read the Python stubs at all. The argument for accepting those limits is above, and if it stops
holding, the thing to build is the Python regenerate-and-diff, which is known to work and known to
be free.

### Proven able to fail, at both levels

**Suite: `scripts/stubcheck.py --root ..` run against the real `proto/body.proto` and the real
`body/crates/rpc/src/_generated/cortex.seam.v1.rs`**, one temporary edit at a time, each reverted
with `git checkout --` and the revert asserted before the next. Fourteen rows, all as designed.

| # | mutation | expected | got |
|---|---|---|---|
| 00 | none, the tree as committed | 0 | 0 |
| 01 | the proto comment's stated default edge retuned, stub not regenerated | 1 | 1 |
| 02 | the bracketed range doc line deleted from the stub | 1 | 1 |
| 03 | a comment added to the proto only | 1 | 1 |
| 04 | a service banner reworded in the proto only | 1 | 1 |
| 05 | the bracketed comment reworded in the proto only | 1 | 1 |
| 06 | a service banner reworded in the stub, both copies | 1 | 1 |
| 07 | a service banner reworded in the stub, one of its two copies | 0 | 0 |
| 08 | the file header above `syntax` reworded (must stay green) | 0 | 0 |
| 09 | a proto rule line shortened (must stay green) | 0 | 0 |
| 10 | a doc comment the proto never wrote added to the stub (must stay green) | 0 | 0 |
| 11 | the proto emptied | 2 | 2 |
| 12 | the proto removed | 2 | 2 |
| 13 | the stub emptied | 2 | 2 |

Row 01 is the case the gate exists for. Row 07 is a limitation the measurement found rather than
one anybody designed: tonic emits each service banner twice, once for the client module and once
for the server, so rewording one copy leaves the other matching the proto and the gate passes. It
is recorded in
[R-434](../refinements/tasks/434-the-stub-check-reads-one-direction-and-one-stub.md) with the
other two gaps.

**Suite: `scripts/tests/test_stubcheck.py` and `scripts/tests/test_protocomments.py`, 54 tests**,
run against a mutated gate and restored after each. Baseline 54 passed. Fourteen mutants planted
and fourteen killed: bracket unescape dropped (11 failed), heading strip dropped (5), rule
collapse dropped (6), header read as body (5), string awareness dropped so a `//` inside a literal
opens a comment (3), a block comment walked past instead of refused (1), trailing comments not
collected (6), every comment recorded as leading (4), a plain `//` line counted as a doc comment
(4), the empty-proto floor dropped (1), the empty-stub floor dropped (1), no miss ever reported
(6), the CLI exiting 0 with misses on the page (1), and an unreadable input swallowed (4).

The gate lands green over 208 proto comments (177 leading, 31 trailing) sought among 338 doc
comment lines, so it reports no drift in the tree as committed and is in place for the next
skipped regeneration.

## Addendum (2026-08-25): the comparison counts copies, and the other two gaps are declined

The gate above shipped with three recorded gaps, and this settles all three. One is closed,
because it cost less than the note recording it estimated; the other two are declined, with the
argument here so nobody re-derives it.

**Closed: a service comment is now owed two copies rather than one.** The note estimated that this
needed a reader for the stub's structure, which is most of the way to parsing generated Rust. It
does not. The number comes from the **proto's** own shape, which the reader already walks: tonic
writes every service into a client module and a server module and documents both from the one
declaration, so a comment inside a `service` block, or in the unbroken run standing directly above
the `service` line, arrives in the stub twice, and every other comment arrives once. Measured
against the tree as it stands, that predicts the stub exactly: of 208 proto comments, 72 are
claimed by a service, and every distinct text is present in at least the copies it is owed. The
rule moves from set containment to a tally comparison, and a miss now names both numbers.

One kind of comment is pinned to a floor rather than counted, the horizontal rule line, which
carries no words. A rule line normalizes to a single token, and prost absorbs the closing rule of a
banner into the setext heading it makes of the line above, so a banner written as three lines comes
out as two, and the number of copies that survive does not follow from the number written.
Counting them would have failed over punctuation on a tree that was fully in sync, so the rule line
keeps the floor of one that containment always held it to. That was measured rather than assumed:
the proto body writes four rule lines, all inside service banners, and the stub holds four rather
than the eight a naive doubling predicts.

**Declined: the reverse direction.** A comment deleted from the proto but still standing in the
stub leaves the gate green, and that is deliberate. The stub carries doc comments prost synthesizes
rather than copies, `Nested message and enum types in ...` among them, so a reverse comparison
needs a list of exceptions, and a genuinely stale comment worded to resemble a synthesized one
would be excused by that list. The deletion case costs a paragraph of prose outliving its
declaration in generated code nobody hand-edits; the exception list costs a permanent hole in the
direction that is checked. The counting rule above also recovers most of the deletion case, since a
comment reworded in the proto is a miss in the checked direction, and a comment still in use gets
reworded far more often than it gets deleted.

**Declined: the Python stubs, again and on the same evidence.** The regenerate-and-diff was
measured before the gate shipped and declined then; the note asked whether the structural drift
that produces no other error earns a codegen run on every brain change, and asked for the run to be
timed first. Timed on this tree with a warm venv, `grpcio-tools` regenerating all three files into
a temporary directory took 0.08s and the `.pyi` came out byte identical to the committed one, so
cost was never the argument. The argument is what the check buys. It covers no comment at all, and
the structural drift it does cover is drift a compiler and pyright already report, except for the
one case of a message or field added to the proto and used nowhere, which by construction is
something no code depends on yet. Buying that with a codegen step
inside the gate, plus a temporary directory and a byte comparison to maintain, is worse than
writing down that `just proto` regenerates both stacks together. If that ever stops being true,
this is the thing to build, and it is known to work.

### Proven able to fail, at both levels

**Suite: `scripts/stubcheck.py --root ..` run against the real `proto/body.proto` and the real
`body/crates/rpc/src/_generated/cortex.seam.v1.rs`**, one temporary edit at a time, each reverted
with `git checkout --` and the revert asserted before the next. Nineteen rows, all as designed.
The number is the process exit code.

| # | mutation | expected | got |
|---|---|---|---|
| 00 | none, the tree as committed | 0 | 0 |
| 01 | proto's stated default edge retuned, stub not regenerated | 1 | 1 |
| 02 | the bracketed range doc line deleted from the stub | 1 | 1 |
| 03 | a comment added to the proto only | 1 | 1 |
| 04 | a service banner reworded in the proto only | 1 | 1 |
| 05 | the bracketed comment reworded in the proto only | 1 | 1 |
| 06 | a service banner reworded in the stub, both copies | 1 | 1 |
| 07 | a service banner reworded in the stub, one of its two copies | 1 | 1 |
| 07b | the other copy of that banner reworded instead | 1 | 1 |
| 07c | a service method comment reworded in one of its two copies | 1 | 1 |
| 08 | the file header above `syntax` reworded (must stay green) | 0 | 0 |
| 09 | a proto rule line shortened (must stay green) | 0 | 0 |
| 10 | a doc comment the proto never wrote added to the stub (must stay green) | 0 | 0 |
| 11 | one of the stub's four rule doc lines deleted (must stay green) | 0 | 0 |
| 12 | every rule doc line deleted from the stub | 1 | 1 |
| 13 | a message field comment's only copy reworded in the stub | 1 | 1 |
| 14 | the proto emptied | 2 | 2 |
| 15 | the proto removed | 2 | 2 |
| 16 | the stub emptied | 2 | 2 |

Rows 07, 07b and 07c cover the limitation this addendum closes: row 07 passed under the old
containment rule. Rows 11 and 12 show the pinned tally holding its floor without asserting a count,
and row 09 shows that the rule collapse is a normalization rather than a special case.

**Suite: `scripts/tests/test_stubcheck.py` and `scripts/tests/test_protocomments.py`, 67 tests**
(54 before this change), run against a mutated gate and restored from a copy after each. Baseline
67 passed, 0 failed. Twelve mutants planted in the new logic and twelve killed: no comment ever
claimed by a service (4 failed), the banner above a service line not claimed (3), a blank line no
longer detaching the run (1), the claim outliving the block that opened it (3), a code line no
longer ending the run (1), a service comment owed one copy like any other (1), the rule tally
summed instead of pinned (7), the rule tally exempting instead of flooring (2), the comparison
reduced to containment again (2), a miss reported per comment rather than per text (3), the two
numbers a miss names swapped (4), and the doubled reading never counted (2).

Both suites are stdlib-only and need no `protoc`, no docker and no GPU, so the gate still runs
everywhere `just check` does, CI included.

## Addendum (2026-08-26): the live roster is held to the suite, and its tally is dropped

Decision 3 above put the live seam checks in an `#[ignore]`d suite that no gate runs: not in CI,
not under coverage, started by hand with `just seam-health`. That is the right shape, and it has a
cost the decision did not account for. Every other suite in this repo documents itself, because a
reader encounters it by running it. This one is encountered instead as the roster in
[modules/body-rpc.md](../modules/body-rpc.md), which is the only description of it a reader gets
without opening the file, and which is what a reader decides from whether to open the file at all.
Nothing held that description to `body/crates/rpc/tests/live.rs`.

### Re-derived first, and the roster is right today for the second time

Measured over the tree before anything changed. `tests/live.rs` carries eight `#[ignore]`d tests
and the roster names those eight, so the two lists agree at this moment. Agreement today is not an
argument against the entry, because the divergence is recurring. The roster once opened by saying
"Two `#[ignore]`d tests run against a real brain" while describing four, when the suite carried
seven, after several passes that each added a check and left the sentence alone. Two passes since
then repaired it by hand, the second on the day before this one, and neither repair added anything
that would catch the third divergence. The list stays correct only while someone remembers to
update it.

The tally in front of the list drifted first, and it drifted twice: the count and the list
disagreed with each other, and both disagreed with the file.

### What a roster is, and what is held about one

A **roster** is a list of names a document keeps for a set the tree really holds. Three of them
are registered now, the live checks here and two in the `scripts/` contract (ADR-0029
roster-membership addendum), and `scripts/rostercheck.py` holds each to the thing itself:

- **membership**, every member of the real set is named on the page;
- **naming**, every name on the page is a member.

Nothing else. The sentence beside each name says what that check proves and why it is shaped the
way it is, which is the value of the list and the part a generated list could not supply. Forcing
that prose into a machine-readable table would cost the list its purpose, so the prose stays free:
any wording, any length, any order. Reordering the eight bullets, rewriting every sentence, and
changing a bullet from a fact about the check to a fact about the brain all leave the gate green.

**The tally is dropped rather than rendered.** The entry offered both, and dropping it is the
better of the two. A number restated by hand beside the list it summarises is a second copy of the
same claim with none of the detail, and it goes stale on the same edit; a reader who wants the
count can count the bullets, which the gate now guarantees to be the whole set. The sentence that
replaced it states the two things the number was conveying poorly: that the roster is every live
check and nothing else, and that not all of them need a running brain, which each bullet now says
for itself.

### Why a scan of its own rather than an existing one

`crosscheck.py` ties a **value** spelled in more than one place. A roster is not a value: the far
side is a set nobody spells anywhere, derived by reading a directory or a run of attributes, and
the near side is a list rather than an occurrence. Registering eight test names as eight constants
would be eight entries that never disagree with anything, since the suite declares no name a
registry could read.

`backlogcheck.py` already reads documents, and it reads them for **pointers**: a link that
resolves, a fragment that names a heading its target offers. Widening it to membership would put
two unrelated questions behind one flag and one exit code. The two gates run side by side and do
not overlap: renaming a heading this record carries, while a task file points at it, fails the
backlog gate and leaves the roster gate green; a bullet in the live roster losing its name fails
the roster gate and leaves the backlog gate green.

### How a roster is written down, and where it begins

`scripts/rosters.py` is the registry and `rostercheck.py` is the scan, the same split the constant
registry uses: a roster arrives as one entry plus, when its set is a new kind, one reader in
`rostermembers.py`, and the scan never learns which document or which shape it is reading.

Two decisions inside that are worth recording. **A passage is bounded by two phrases the document
already carries**, each exactly once, because bounding by heading would put both of the `scripts/`
contract's rosters into one section, where a name missing from one list would pass on the strength
of the other, and bounding by paragraph cannot reach a list that opens with a fenced command. A
boundary phrase that stops appearing, or starts appearing twice, is itself a reported fault, so an
edit that moves a boundary fails the gate rather than silently narrowing what is compared. **Names
are read in one of two shapes**, a bullet's first code span or every code span matching the
roster's own pattern, because a roster that explains each member is a list and a roster inside a
running sentence is not, and forcing either into the other's shape would make the gate dictate the
prose.

### Proved able to fail, fourteen mutants over the real tree

**Suite: `scripts/rostercheck.py --root ..` run against the real `body/crates/rpc/tests/live.rs`,
the real [modules/body-rpc.md](../modules/body-rpc.md) and the real
[modules/repo-gates.md](../modules/repo-gates.md)**, one temporary edit at a time, each restored
from a copy taken before the first and the restore asserted by the next clean row. The number is
the process exit code.

| # | mutation | expected | got |
| --- | --- | --- | --- |
| 00 | none, the tree as committed | 0 | 0 |
| 01 | a ninth live check added to the suite, the roster left alone | 1 | 1 |
| 02 | a live check renamed in the suite only | 1 | 1 |
| 03 | a live check renamed in the roster only | 1 | 1 |
| 04 | a roster bullet stripped of its name | 1 | 1 |
| 05 | a roster bullet's prose reworded (must stay green) | 0 | 0 |
| 06 | the live roster's opening phrase reworded | 1 | 1 |
| 07 | the live roster's closing phrase reworded | 1 | 1 |
| 08 | a tenth registry part added on disk, both lists left alone | 1 | 1, two faults, one per roster |
| 09 | one part struck from the tuple list | 1 | 1 |
| 10 | two modules struck from the contract's own listing | 1 | 1 |
| 11 | a module renamed in the contract and not on disk | 1 | 1, both directions at once |
| 12 | the parts roster's opening phrase reworded | 1 | 1 |
| 13 | the live suite removed | 2 | 2 |
| 14 | every ignore in the live suite disarmed | 2 | 2 |

Rows 01 and 08 are the two directions the backlog entries described, and the gate failed on both
the day it landed. Row 05 shows that the prose beside each name is free, and row 04 that a bullet
losing its name is a fault rather than a member silently dropping out of the roster. Rows 13 and 14
are the floors, which exist because a comparison over an empty set would otherwise pass forever.

The suite behind the scan was mutated too: sixteen mutants over `scripts/tests/`, fifteen killed
and the survivor recorded rather than removed. That table is in the ADR-0029 roster-membership
addendum, with the second half of the decision.

### What this opened

The scan reads three rosters and the repo writes more lists than that. The nearest is the list of
cross-tree scans themselves, spelled in seven places across a README table, two YAML comments, a
justfile comment, this repo's contract twice and a module doc, one of which was found short a scan
while this was being written
([R-446](../refinements/tasks/446-the-scan-roster-is-spelled-in-seven-places.md)). A second is
narrower and lives inside the mechanism: a boundary phrase moved to a wider point in its own
document is only caught when the wider passage happens to break some other rule
([R-447](../refinements/tasks/447-a-widened-passage-is-caught-only-by-accident.md)).

### Records

This change is recorded in:

- the task file
  [R-442](../refinements/tasks/442-nothing-holds-the-live-check-roster-to-the-suite.md), which
  closes as landed, and [docs/refinements/index.md](../refinements/index.md), regenerated from it;
- `scripts/rostercheck.py`, `scripts/rosters.py`, `scripts/rosternames.py` and
  `scripts/rostermembers.py`, the new gate and its three parts, with
  `scripts/tests/test_rostercheck.py`, `scripts/tests/test_rosternames.py` and
  `scripts/tests/test_rostermembers.py`;
- [modules/body-rpc.md](../modules/body-rpc.md), whose live roster loses its tally and gains the
  sentence saying what holds it;
- [modules/repo-gates.md](../modules/repo-gates.md), which documents the new gate and is now one of
  the two documents it reads;
- the justfile and the CI workflow, which run it beside the other cross-tree scans;
- [AGENTS.md](../../AGENTS.md), [README.md](../../README.md) and
  [docs/index.md](../index.md), which count and name the scans;
- and this addendum.

## Addendum (2026-08-26): the scan roster is held to the recipes that run it

The live-roster addendum above built a scan holding a document's roster to the set it describes,
registered three rosters, and closed by naming the nearest list it did not reach: the cross-tree
scans themselves, spelled in seven places and found already short a scan in one of them while the
mechanism was being written. That list is held here, in the three places that spell names.

### Re-derived first, and there are eight copies rather than seven, one of them stale today

Measured over the tree before anything changed. The entry counted seven copies and undercounted by
one, and the eighth copy is the one that had gone stale. The eight fall into three kinds:

- **three spell the names.** The gate list in [AGENTS.md](../../AGENTS.md) named nine of the ten in
  code spans and wrote the tenth as "the line cap"; the `cross-tree` job comment in
  `.github/workflows/ci.yml` names all ten as bare words; and the module-doc line in
  [docs/index.md](../index.md), which the entry did not count at all, named eight, missing
  `defaultcheck.py` and `backlogcheck.py`, and called `backlogcheck.py` the fifth cross-tree scan
  when it is the tenth. So a copy was stale on the day this was picked up, for the second time in
  this list's short history, and again it was a copy nobody had counted.
- **two describe them.** The header comment of the same workflow and the Purpose paragraph of
  [modules/repo-gates.md](../modules/repo-gates.md) both run through the ten as phrases, the
  punctuating-dash ban and the compose defaults check, naming no module at all.
- **three carry only a tally.** The `just check` row in [README.md](../../README.md), the comment
  above the `check` recipe, and the justfile line of the repo map each say how many there are.

### What a cross-tree scan is, which is the part with no directory to read

Every other set a roster is held to can be read from a directory listing. This one cannot:
`contrast.py` sits in `scripts/` and gates nothing, `composefiles.py` is read by three gates and
run by none, and `check-shell` is a recipe CI schedules that the single gate deliberately does not
run (ADR-0011 shell-clippy addendum). What makes a module a cross-tree scan is that **`just check`
runs it before the per-tree checks and CI's `cross-tree` job runs it too**, which is a fact about a
justfile and a workflow.

`scripts/scanrecipes.py` reads both. The gate side is the unbroken run of `just check-*` lines the
`check` recipe opens with, which stops at the first command that is not one, so the four trees
below it are outside the set however they are launched. The CI side is every `- run:` step of that
job, each of which must be one of those recipes; a step that is not raises. A recipe is mapped to a
module through its own body, since the two names differ: `check-backlog` runs `backlogcheck.py`.

**A disagreement between the two files is a fault rather than a union.** Taking either side alone
would let a document agree with the half that had moved, which is the failure being closed one
level up. The two are compared as sets, since these scans are independent of each other and the
order each file runs them in does not matter.

### Which copies are held, and the argument for the ones that are not

The three that spell names are registered, in two shapes. Two are read as code spans, and the third
is the workflow comment, read as bare words, which settles the other half of the decision the entry
left open: **a comment counts as a roster when it names its members.** Reading a YAML comment needs
no parser, since the boundary phrases delimit the passage, and the alternative was to declare the
one copy that had actually gone stale out of scope.

Two edits made those copies readable, and both improve the documents on their own terms. The gate
list now spells `linecap.py` beside the nine siblings it already spelled, and the index line spells
the scans as file names, which is how every other document in this repo names them. Neither edit
bends a document to suit the gate: no sentence changed its claim, and the passages are bounded on
phrases that carry no tally, so a scan can be added without editing the registry.

The other five are left alone, for two different reasons.

**The three tallies follow the standing decision.** A document's numbers are its own business
(ADR-0029 registry-parts addendum, widened to say that the decision covers numbers and not names in
the roster-membership addendum). Nothing changes here.

**The two descriptions are declined rather than deferred without comment.** A roster written as
phrases has no names to hold, and the only way to hold it would be to rewrite both passages into
lists of module names. That would cost the Purpose paragraph its job of saying what this tree is
rather than which files are in it, and cost the header comment the argument it makes for the job
below it. It is recorded as
[R-452](../refinements/tasks/452-a-roster-written-in-descriptions-is-held-by-nobody.md), because
the descriptive copy in that header is precisely the one that was found short a scan, so the
residue is real even though the cheap fix is worse than the problem.

### Proved able to fail, thirteen mutants over the real tree

**Suite: `scripts/rostercheck.py --root ..` run against the real [AGENTS.md](../../AGENTS.md), the
real `.github/workflows/ci.yml` and the real [docs/index.md](../index.md), with the real justfile
and workflow as the far side**, one temporary edit at a time, each restored from a copy taken
before the first and the restore asserted by a clean row at the end. The number is the process exit
code, and the note beside it is how many faults that run printed.

| # | mutation | expected | got |
| --- | --- | --- | --- |
| 00 | none, the tree as committed | 0 | 0 |
| 01 | an eleventh scan wired into both files, no document touched | 1 | 1, three faults |
| 02 | a scan wired into the gate and not into CI | 2 | 2, the two files disagree |
| 03 | a scan wired into CI and not into the gate | 2 | 2, the same refusal from the other side |
| 04 | one scan struck from the engineering contract's list | 1 | 1 |
| 05 | one scan struck from the workflow's own comment | 1 | 1 |
| 06 | one scan struck from the documentation index | 1 | 1 |
| 07 | a scan renamed in the contract only | 1 | 1, both directions at once |
| 08 | a recipe repointed at another module, no document touched | 1 | 1, six faults |
| 09 | the contract's opening phrase reworded | 1 | 1 |
| 10 | the workflow comment's opening phrase reworded | 1 | 1 |
| 11 | the cross-tree job renamed, which is a boundary and the reader's subject at once | 2 | 2 |
| 12 | the tally in front of the contract's list changed to eleven | 0 | 0 |
| 13 | a scan's description reworded, the name left alone | 0 | 0 |

Row 01 is the defect the entry is about, reported as three faults rather than left for somebody to
notice on a re-read, and it is why this landed as a second commit: adding `scanrecipes.py` to
`scripts/` produced two faults against the module listings held one commit earlier, before those
documents were updated. In rows 02, 03 and 11 the reader raises rather than answering, which exits
2 rather than 1 and names the two lists that disagree. Row 08 fails against all three copies twice
over, because the repointed recipe both loses a member and adds one. Rows 12 and 13 show the tally
and the prose staying free.

### Proved able to fail, eleven mutants over the scripts suite

**Suite: `scripts/tests/`, 1244 tests** (1221 before this change), which is the collection every
count below is out of. One mutant at a time, each restored from a copy taken before the first, with
`__pycache__` purged between runs, and the baseline re-established after the last row. Eleven
mutants, eleven killed.

| # | mutation | expected | observed |
| --- | --- | --- | --- |
| 00 | none, the tree as written | the baseline | 1244 passed |
| 01 | the gate's run is read from the whole recipe rather than from its opening | the stop test fails | 1 failed, 1243 passed |
| 02 | a block ends only at column zero | the sibling job test fails, and the real tree with it | 9 failed, 1235 passed |
| 03 | a step the job was not taught is stepped over | the refusal test fails | 1 failed, 1243 passed |
| 04 | a recipe running two modules answers with one of them | the two-module test fails | 1 failed, 1243 passed |
| 05 | the two files are merged rather than compared | both disagreement tests fail | 3 failed, 1241 passed |
| 06 | a recipe's name is trimmed instead of its body being read | the real tree fails, and the differing-name test | 5 failed, 1239 passed |
| 07 | the scans may come back empty | the floor test fails, and the rosters over it | 6 failed, 1238 passed |
| 08 | INTERACTION: the workflow comment is registered as a spelled roster | the real tree fails | 3 failed, 1241 passed |
| 09 | INTERACTION: the scan rosters are held to the modules in scripts/ | the real tree fails | 4 failed, 1240 passed |
| 10 | the workflow roster is dropped from the registry | the multi-shape test fails | 1 failed, 1243 passed |
| 11 | a recipe header may carry no parameters | the parameter test fails | 2 failed, 1242 passed |

Row 02 is the mutant that was a real defect first. The block reader originally ended a block at the
first unindented line, which is right for a justfile recipe written at column zero and wrong for a
workflow job, since every job is written under one key: the first reading reported fifteen recipes
for the `cross-tree` job, having read past every job below it, `check-shell` and the per-tree
checks included. The depth is now read off the header, and this row holds that fix in place.

Rows 08 and 09 are the interaction rows, aimed at the seam between this set and the machinery it
arrives in: the bare-word reading swapped back to the code spans the older rosters use, which finds
nothing in a YAML comment, and the new rosters pointed at the members reader the older ones use,
which is the mistake of holding a scan list to a directory listing.

### Records

This change is recorded in:

- the task file
  [R-446](../refinements/tasks/446-the-scan-roster-is-spelled-in-seven-places.md), which closes as
  landed, and [docs/refinements/index.md](../refinements/index.md), regenerated from it;
- `scripts/scanrecipes.py` and its suite, the reader that returns what the scans are, and
  `scripts/rostermembers.py`, which offers that answer to a roster;
- `scripts/rosters.py`, which registers the three copies;
- [AGENTS.md](../../AGENTS.md), whose gate list now spells every scan it names and whose repo map
  gains the new module;
- `.github/workflows/ci.yml`, whose job comment is now a held roster;
- [docs/index.md](../index.md), which was two scans short and is repaired;
- [modules/repo-gates.md](../modules/repo-gates.md), which documents the new module;
- and this addendum.
