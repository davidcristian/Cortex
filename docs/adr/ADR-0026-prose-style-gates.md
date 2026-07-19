# ADR-0026: Prose style gates (no dash as punctuation, no volatile references)

- **Status:** Accepted
- **Date:** 2026-07-11

## Context

Two rules govern the repo's prose. Neither had a gate, so both were only convention:

1. **No dash as punctuation.** Prose here does not use an em dash.
2. **No volatile references in a commit message.** A message must still read correctly
   once the planning docs move on, so it may not cite a slice number, a decision-record
   number, the roadmap, or any numbered pointer into a mutable doc.

Convention was not enough. A history sweep found **3452** distinct lines using an em dash
across every commit, and **144 of 148** commit messages violated at least one rule. Both
numbers are what an unenforced style rule looks like after a few months: prose is
rewritten constantly, and the dash is the default output of nearly everything that writes
it. AGENTS.md states both rules, but `just check` is the single gate, and it checked
neither. A rule with no gate is a defect by the repo's own standard.

The rules are also easy to enforce *wrongly*. During the sweep, the ad-hoc verifier
raised false positives twice: once on an en dash inside a numeric range, once on the SQL
comment marker at the head of a line. Both are correct text that a naive scan condemns. A
gate that cries wolf gets disabled, so the boundary needs to be exact.

## Decision

Add `scripts/dashcheck.py` (cross-tree, in `just check` and unconditionally in CI, like
the line cap) and extend `scripts/commitlint.py` from the header to the whole message.

1. **The em dash and the en dash are both banned outright; U+2212 MINUS SIGN is not.**
   The first cut of this ADR banned the en dash only when spaced, on the grounds that an
   unspaced one is a range (a 2-4B model, 0.15-0.27 GB) and therefore correct typography
   rather than punctuation. That reasoning was sound but beside the point: the rule exists
   so prose reads as typed, and a plain ASCII hyphen is how a range is typed. All 49 en
   dashes in the tree were ranges, every one took a hyphen without loss, and the rule got
   simpler for it. The minus sign stays legal, since forcing `-` on a subtraction would
   make the arithmetic wrong rather than plain.

   This is a substitution, which the em-dash rule forbids. The distinction is that an em
   dash *punctuates*, so swapping in a comma leaves a worse sentence and the fix is to
   restructure. A range does not punctuate anything; the hyphen is simply its ASCII
   spelling.

2. **ASCII `--` is banned in a commit message and allowed in a file.** The two are
   different registers. A commit message is pure prose, so ` -- ` there is an em dash in
   ASCII clothing. A source file uses `--` as this repo's inline-reason idiom
   (`# noqa: DTZ001 -- the naive value under test`, `# pragma: no cover -- reason`), which
   the escape-hatch rule effectively requires and which appears across 13 files. Banning
   it in files would mean either abandoning that idiom or an unrequested second sweep.
   `commitlint.py` owns the strict register; `dashcheck.py` owns the lax one.

3. **`dashcheck.py` scans every text file, and does not skip tests or `_generated`.**
   The line cap skips both, because a 400-line test is not the problem the cap targets.
   Prose is different: a comment in a test is prose, and a generated stub carries the
   proto's comments verbatim. The rule follows the prose, not the compiler.

4. **The escape hatch is an inline `dashcheck: allow` plus a reason**, mirroring
   `# pragma: no cover -- reason`. It exists for a dash that *means* rather than
   punctuates. The repo has exactly one: an HTML test asserting `&#8212;` decodes to the
   literal character, where rewriting the dash would invert the assertion.

5. **The gates spell dashes as `\uXXXX` escapes**, in their own source and their tests.
   A gate that names a forbidden character must not contain it, or it flags itself. This
   is the alternative to exempting the gate's own files, which would leave a hole exactly
   where the rule is defined.

6. **A commit hash is flagged only when it resolves**, via `git cat-file` against the
   repo. A rewrite invalidates a cited hash, which is precisely why the rule exists (the
   sweep found two dangling ones). But hex strings are also action pins and digests, which
   are legal. Resolving the token separates the two exactly, with no heuristic. If `git`
   is unavailable the check cannot disprove the hash and passes, since a hook that blocks a
   commit on its own inability to check is worse than the miss.

7. **Git-generated headers (`Merge `, `fixup! `, …) are exempt from the body rules too.**
   That wording is git's, not the author's, so holding it to an authored-prose rule would
   fail commits nobody wrote.

## Consequences

- The rules now fail the build instead of degrading silently. Both were verified to fail
  on a real violation before being trusted: an em dash reintroduced into a doc and into a
  Python docstring, and a message citing a slice number, a decision record, and a live
  commit hash.
- Prose loses a mark. Restructure the sentence rather than swapping in another; a comma
  where an em dash was is usually a worse sentence, not a fixed one.
- `commitlint.py` now shells out to `git`, so it is no longer purely hermetic. It stays
  stdlib-only and degrades to passing when git is absent, so the commit-msg hook still
  runs under a plain `python3` with no environment sync.
- The volatile-reference ban is deliberately blunt: it rejects the word "roadmap"
  outright. A commit that genuinely edits the plan must describe what it changed rather
  than name the file. That is the intent, and it is the rule's sharpest edge.
- The dash rule is not retroactively enforceable on anything outside this repo's history,
  and the one allowed exemption is load-bearing: if the HTML entity test moves, its pragma
  moves with it.

## Deferred

- **`scripts/pyproject.toml` is fail-open and it bit while writing this.** The pytest
  `--cov=` list and pyright's `include` both enumerate modules by name, so `dashcheck.py`
  escaped the coverage gate and strict typing until the omission was caught by eye. The
  tree still read 100%, since an unmeasured module cannot lower an average. Measuring the
  tree instead of a list is the fix; recorded in the ROADMAP's deferred-refinements
  section. Until then a new script must be hand-added to both lists or it is ungated.
  *Closed by the 2026-07-12 addendum below.*

## Addendum (2026-07-12): the fail-open gate config is closed

The deferred item above is done. `scripts/pyproject.toml` now measures the tree instead
of a list on both fronts. pytest-cov runs `--cov=.`, under which coverage discovers every
`*.py` file in the tree, so a script no test imports reports 0% and fails the 100%
threshold instead of being invisibly absent from an average. An explicit
`[tool.coverage.run] omit` keeps `tests/` and `.venv/` out, preserving the prior
semantics (test files were never measured). pyright's `include` is now `"."`, with an
explicit `exclude` for `.venv`, `__pycache__`, and `.pytest_cache`. Escaping either gate
now requires writing an exclusion, never forgetting an addition, which is the fail-closed
posture every other classifier in `scripts/` already had.

Proven to fail before being trusted, per the repo's distrust-green rule: a probe script
(an untested, untyped function added to no list) dropped total coverage to 98.62% and
failed pytest, and raised two strict-mode pyright errors; with the probe removed,
`just check-scripts` passes at 100%.

## Addendum (2026-07-18): the commit body's wrap is convention, not gate, and now says so

An audit of a `Health` repair measured what this ADR's own gate does not cover.
[AGENTS.md](../../AGENTS.md) states one width rule for a commit message, "the body explains what
and why, wrapped at 72", and `scripts/commitlint.py` checks `MAX_HEADER_LENGTH = 72` against the
header alone. The body is walked line by line for dashes and volatile references and its width is
never read. The drift that follows is exactly what an unenforced rule looks like: over the seven
most recent commits at the time of the audit, every single one had body lines past 72, the worst
at 77, spread across authors and slices rather than concentrated in one change.

**Not fixed here, and the reason is the exceptions rather than the check.** Adding a width test to
the walker that already reads every line is two lines; deciding what a hard wrap may not touch is
the actual design. A URL, a pasted command, a fenced code block, and a `BREAKING CHANGE:` footer
can each legitimately exceed 72 and must not be reflowed, so a naive gate would fail correct
messages and push authors toward mangling them. The cost of leaving it is cosmetic (`git log` in a
narrow pager wraps long lines, it does not truncate them), which is why this is recorded with a
trigger rather than built.

It is a deferral in the ordinary sense and is recorded in all three places this repo requires: the
entry lives in [docs/refinements/repo-gates.md](../refinements/repo-gates.md) beside this ADR's
other prose-style items, its line is in [docs/refinements/index.md](../refinements/index.md) under
fix-when-it-bites, and this addendum is the origin record. Until it lands, the 72-column body wrap
stands as convention exactly the way imperative mood does under this ADR's decision: stated in
AGENTS.md, checked by nobody, and now honestly labelled as such rather than cited as a gate.
*Superseded by the 2026-07-19 addendum below: the check landed, and one of the four exceptions
above landed with it.*

## Addendum (2026-07-19): the body wrap is a gate now, and three of its four exceptions are not

The deferral above is closed. `scripts/commitlint.py` gained `MAX_BODY_WIDTH = 72` and now measures
every line **below** the header inside the walk that already read each line for dashes and volatile
references, which is exactly the "one more check in the same walker" the entry predicted. The
header keeps its own cap in `check_header`, so one long subject draws one complaint rather than
two. The rule this ADR called convention is therefore a gate, and the sentence above about it being
"checked by nobody" no longer describes the repo.

**One exception shipped, and it is a word-width rule rather than a line-kind rule.** `too_wide`
exempts a line past the wrap whose **longest word alone** exceeds it, on the reasoning that a URL,
a path, or a long identifier has nowhere to break, so demanding a rewrite that cannot exist would
train authors to ignore the gate. That covers the first of the four classes named above. It does
not cover the other three, and the difference is structural rather than an oversight in the
wording: a pasted command and a fenced code block are built out of ordinary short words, so the
longest-word test sees nothing unusual about them.

**Measured against the shipped gate on 2026-07-19, rather than argued.** One message carrying an
indented `docker compose --project-directory . -f docker/docker-compose.yml ... up -d` line (108
chars, longest word 29), a fenced `uv run pytest packages/core --cov ...` line (82 chars), and a
`BREAKING CHANGE:` footer of short words (118 chars) produced three complaints and exit 1. The
footer is the sharpest of the three in principle, because [AGENTS.md](../../AGENTS.md) mandates
that footer for a breaking change, so the gate as it stands can refuse a message the commit rules
themselves require; it is also the easiest to live with, since a footer is prose and its value may
carry newlines, so wrapping it costs nothing. A pasted command and a fenced block cannot be
reflowed without changing what they say, which is the "rewriting messages rather than checking
them" failure the deferral named.

Closing that gap wants a **line-kind** exemption rather than a word-width one: a fence toggle
carried through the walk, a heuristic for a pasted command (a leading indent, a shell prompt), and
a decision on whether a footer is exempt at all or simply wrapped like any other prose. That is
recorded as its own deferral in the three places this repo requires, replacing its parent: the
entry in [docs/refinements/repo-gates.md](../refinements/repo-gates.md), its line in
[docs/refinements/index.md](../refinements/index.md) under fix-when-it-bites, and this addendum.

**Why this addendum exists at all is worth stating.** The landing changed a gate's behaviour, and
updated AGENTS.md and the repo-gates module doc, while touching no deferral record: the entry, the
index and this ADR all went on saying the rule was ungated. It is the only commit in the last fifty
to move a gate without moving a record, which is precisely what the doc-first Definition of Done
exists to prevent, and it is why the correction is three edits rather than one.
