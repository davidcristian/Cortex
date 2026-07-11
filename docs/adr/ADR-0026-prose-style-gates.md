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

1. **The em dash is always punctuation; the en dash only when spaced.** An unspaced en
   dash is a range (a 2-4B model, 0.15-0.27 GB), which is correct typography, and U+2212
   MINUS SIGN is arithmetic. Neither is punctuation, so neither is flagged. This is the
   precise form of the false positive the sweep hit, and the reason the gate keys on
   spacing rather than on the character alone.

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
