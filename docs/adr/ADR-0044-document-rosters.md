# ADR-0044: Document rosters compared with the tree

**Status:** Accepted (2026-09-15)

## Context

Several documents keep a list of names for a set the tree really holds: the modules in `scripts/`
and the parts of the constant registry in the repo-checks module contract, the cross-tree scans in
AGENTS.md, the CI workflow and the docs index, the brain's packages and the body's crates in the
repo map. Each name has a sentence beside it saying what the member is for, which is why the list is
written by hand. Nothing compared the list with the set, so a member added without the list, or a
name kept after its subject was renamed, went unnoticed until a reader went looking.

The scan was first built for the live RPC tests of [ADR-0003](ADR-0003-generated-stubs.md), whose
list in the body's RPC module doc had fallen out of date with the suite more than once, and the list
of cross-tree scans followed. The decisions on names and forms were taken where the constant
registry was then recorded; all of them are here, one subject in one record.

The question they answer came from the registry: it had decided that a document describing a check
is not a second place for that check's values, so a count in the check's contract stays unchecked.
Whether that covered a list of names as well as a count was open.

## Decision

1. **Names are compared; counts are not.** A count goes stale on any edit anywhere, including edits
   that change nothing the document says, so checking one would make a check out of arithmetic
   nobody reads. A name list goes stale on exactly one edit, adding or renaming a member, which is
   the edit that should fail. The registry's decision covers numbers only
   ([ADR-0042](ADR-0042-cross-tree-constant-registry.md)); the count words in a roster passage stay
   hand-written and unchecked.
2. **What is compared is membership and naming, both ways.** Every member of the real set is named,
   and every name is a member or a declared reference. The sentence beside a name is free in length
   and order. A roster is one entry in `rosters.ROSTERS`: a label and a reason printed with any
   fault; the document; two phrases bounding the passage it occupies, neither of which may be a
   member's name; the form a name is written in; and the reader in `rostermembers.py` that returns
   the real set. A new kind of set arrives as a new reader, and the scan is never told which
   document or layout it is reading.
3. **The repo-checks module listing is two rosters.** A `scripts/` module has a CLI exactly when it
   has a top-level `if __name__ == "__main__":`, and `rostermembers.py` returns, for the whole tree,
   the modules with that guard and those without. The contract's paragraph names the first half,
   then the second after one phrase (`**The rest have no CLI of their own**`) that closes one roster
   and opens the other, so a module named in the wrong half fails. The `<SUBJECT>_COUPLINGS` names
   in the same contract are a further roster, derived from the part file names through the
   convention `registry.py` declares.
4. **A roster may borrow names it does not own.** `refers_to` declares a set whose names a passage
   may use as references: the sentence about the modules with no CLI says whose reader each one
   is, and that name belongs to the other half. Borrowing widens what a passage may name, never
   what it may leave out, so a module that gains a CLI and stays in the second sentence is still
   reported by the first. Which direction a borrowed name's sentence points stays unread.
5. **Three written forms.** `Bulleted` reads a list; `CodeSpans` reads code spans matching a pattern
   (a module is a bare `name.py`, a part a `*_COUPLINGS` tuple name); `Bare` reads every whole word
   in the passage matching the pattern, with a guard that a match touching a word character is
   inside a longer word (a slash beside it is fine). `Bare` exists for the repo map, whose fenced
   block has no code spans.
6. **The repo map's workspace rows are rosters.** In the `brain/packages/` and `body/crates/` rows,
   a member is a name followed, after a space or a line break, by its parenthesised description.
   `(planned) shared` has its marker before the name and nothing after, so it is not a member;
   `cfg(windows)` has no space and is prose. Members are directories, not manifest package names.
7. **The live RPC tests are a roster.** The list in [body-rpc](../modules/body-rpc.md) is the only
   description of `body/crates/rpc/tests/live.rs` a reader gets without opening it, since no check
   runs that suite, so it is compared with the file's `#[ignore]`d tests. Its count is dropped
   rather than checked: a reader who wants the count counts the bullets, which the check guarantees
   are the whole set, and each bullet says for itself whether it needs a running brain.
8. **The roster scan is a check of its own.** `crosscheck.py` compares a value written in several
   places, and a roster's other side is a set nobody writes out, read off a directory or a run of
   attributes. `backlogcheck.py` reads documents for pointers, and membership is a different
   question behind a different exit code. The two run side by side without overlap.
   `scripts/rosters.py` is the registry and `rostercheck.py` the scan, the same split the constant
   registry uses.
9. **A passage is bounded by two phrases the document already contains, each exactly once.**
   Bounding by heading would put two rosters of one section together, where a name missing from one
   passes on the other, and bounding by paragraph cannot reach a list that opens with a fenced
   command. A boundary phrase that stops appearing or appears twice is a fault, so moving one fails
   rather than silently narrowing the comparison. A real set that reads as empty is a fault too,
   since a comparison over nothing would pass forever.
10. **The cross-tree scans are the modules `just check` runs first and CI's `cross-tree` job runs
    too.** No directory listing answers this: some modules in `scripts/` enforce nothing, some are
    read by checks and run by none, and `check-shell` is scheduled by CI and not run by `just
    check`. `scripts/scanrecipes.py` reads the unbroken run of `just check-*` lines the `check`
    recipe opens with and every `- run:` step of the `cross-tree` job, each of which must be one of
    those recipes, and maps a recipe to its module through the recipe's own body. A disagreement
    between the two files is a fault rather than a union, since a document could otherwise agree
    with the half that moved; they are compared as sets.
11. **Three copies of the scan list write the names out, and those are compared.** The list in
    AGENTS.md and the module-doc line in [docs/index.md](../index.md) are read as code spans; the
    comment above the `cross-tree` job in `.github/workflows/ci.yml` is read as bare words, because
    a comment counts as a roster when it names its members. The counts in the README, the justfile
    comment and the repo map stay unchecked, by decision 1.
12. **A description is not a roster.** A passage that runs through the scans as phrases names none
    of them, and checking it would mean registering each phrase per member per document, a
    hand-written copy of a sentence's wording that fails whenever the sentence is reworded;
    counting the phrases would be right only by coincidence and would name nothing when it failed.
    The workflow's header therefore no longer lists the scans: it keeps its argument that they are
    exempt from the path filter and points at the checked comment below it, because it was that
    unchecked second copy that fell out of date both times the list was found short. The Purpose
    paragraph of the [repo-checks module doc](../modules/repo-checks.md) stays prose, left to the eye
    ([R-631](../refinements/tasks/631-the-purpose-paragraph-describes-the-scans-by-eye.md)).

## Consequences

- A module, part, scan, package or crate added without its line in each listing fails the check the
  day it is committed, which is how a new registry part comes to be named in four places.
- A boundary phrase moved to a later line still appears once, so the passage silently widens. That
  can only ever let a roster see more names, never fewer; it is recorded under
  `docs/refinements/tasks/`.
- The success line states the rosters, documents and members the result is over
  ([ADR-0042](ADR-0042-cross-tree-constant-registry.md) decision 19).
- A roster fixes the names in a passage and nothing about its prose, so rewriting the prose around a
  roster is free as long as the bounding phrases and the names survive.

## Alternatives rejected

- **Checking the counts**: decision 1.
- **One roster over the whole module paragraph**: a module named in the wrong half passed.
- **A positional rule for borrowed names** (accepted only as a bullet's first code span): it reports
  correct prose, and widening it means reading grammar.
- **Reading the repo map's fence as the obstacle**: the fence was never the problem; the missing
  code spans were, which `Bare` answers.
- **Manifest package names as workspace members**: the map names directories.
- **Registering each live test as a constant in the registry**: eight entries that never disagree
  with anything, since the suite declares no name a registry could read.
- **Rendering the live roster's count** beside the list: a second copy of the same claim with none
  of the detail, stale on the same edit.

## Related

- Code: `scripts/rostercheck.py`, `rosters.py`, `rosternames.py`, `rostermembers.py`,
  `scanrecipes.py`.
- The [repo checks module doc](../modules/repo-checks.md).
- [ADR-0003](ADR-0003-generated-stubs.md) (the live RPC suite),
  [ADR-0042](ADR-0042-cross-tree-constant-registry.md) (the registry, which covers values and not
  names).
