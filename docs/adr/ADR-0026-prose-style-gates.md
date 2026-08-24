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
entry lives in [docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates) beside this ADR's
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
entry in [docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates), its line in
[docs/refinements/index.md](../refinements/index.md) under fix-when-it-bites, and this addendum.

**Why this addendum exists at all is worth stating.** The landing changed a gate's behaviour, and
updated AGENTS.md and the repo-gates module doc, while touching no deferral record: the entry, the
index and this ADR all went on saying the rule was ungated. It is the only commit in the last fifty
to move a gate without moving a record, which is precisely what the doc-first Definition of Done
exists to prevent, and it is why the correction is three edits rather than one.

## Addendum (2026-08-06): the core barrel is a package of area sub-barrels, not one capped file

The line cap and the `cortex_core` re-export barrel had been on a collision course for a month,
and they collided twice on 2026-08-06: the session-history summarizer got under 300 lines only by
trimming the barrel's docstring, and an hour later `PLAIN_SECURITY_PREAMBLE` landed with its
barrel export backed out after `scripts/linecap.py` measured the file at 304. That left a public
core constant importable from `cortex_core.untrusted` and from nowhere else, unlike every one of
its siblings, which is the shape of a rule bending code rather than code obeying a rule.

The three options on the record were a sub-barrel per area, the test doubles leaving the top
barrel, and an `__all__` over star imports. The first two only relocate the wall unless every
consumer is rewritten to import from the new place, which is 155 files for the doubles alone. The
third is the one that leaves all of them alone, so it is what landed, in the form the objection
against it did not anticipate: `cortex_core/_surface/` holds eight modules, one per area of the
core (`ports`, `turn`, `tools`, `subagents`, `memory`, `schedule`, `residency`, `fakes`), each
importing its area's names from their defining modules and declaring them in its own `__all__`,
and `cortex_core/__init__.py` re-exports all eight wholesale. `from cortex_core import X` still
reaches all 294 public names, so no call site moved and no behaviour changed.

Two objections had to be answered rather than argued away. **Ruff bans the star import** (F403),
which is what the recorded entry called the blocker; it is now one narrow `per-file-ignores` entry
naming the file and the reason, because the rule's own justification ("unable to detect undefined
names") does not apply to a source module that declares `__all__`. **Pyright strict refuses a
wildcard from a library** (`reportWildcardImportFromLibrary`), which fires because `cortex-core`
resolves through its own editable install; a relative import (`from ._surface.turn import *`)
resolves inside the source tree instead, and the package type-checks clean with no suppression at
all. That is why the barrel is the one place in the brain that imports relatively.

The gate itself is untouched. No suffix was added to the scanner, no exemption was written, and
the AGENTS.md list of what sits outside the cap is unchanged: the barrel went from 300 lines to
18, and each sub-barrel is measured like any other module, the largest at 151. Headroom is now
per area rather than global, which is the real change of shape. A new public name costs a line in
its area's file and none in the barrel, so the surface can roughly quadruple before any single
file is at the cap again, and when one is, the split that relieves it is the ordinary
split-by-responsibility remedy rather than another convention change.

## Addendum (2026-08-08): a fourth cross-tree scan, over compose bind mounts

`scripts/bindcheck.py` joins the line cap, the dash ban and the constant registry as an
unconditional `just check` scan, and it guards a class none of the three could see: a
`docker compose up` creating a host directory for a bind-mount source that does not exist yet,
root-owned, written from inside the container, and sitting in the working tree where `git add -A`
will take it. What lands there is a GGUF or a database dump, so the failure mode is a
multi-gigabyte blob one command away from the index. Two live cases (`models/`, `pgdata/`) were
found and ignored by hand; the third was the reason to write a check instead of remembering
again.

**The rule is not "every bind default must be gitignored"**, which would be false of
`./docker/postgres/init.sql` and of every future bind onto a file the repo ships. It is that a
bind source must resolve **outside** the repo (the user's own disk, none of the gate's business),
or onto a path git **tracks** (an input compose finds rather than creates), or onto a path git
**ignores** (an output, declared as one before it can be written). Git answers both questions
itself, via `ls-files` and `check-ignore`, because a hand-rolled `.gitignore` matcher is exactly
the kind of quiet wrongness that leaves a gate green. `check-ignore` is asked with a trailing
slash, since what compose materializes is a directory and a directory-only pattern (`models/`)
does not match a bare path.

**Both project directories are checked.** A relative bind resolves against the project directory,
which is `--project-directory` when given and the first `-f` file's own directory otherwise: the
`just` recipes pass the repo root, a bare `docker compose -f docker/docker-compose.memory.yml`
passes `docker/`. That is why the repo's ignore entries for these paths are unanchored, and the
scan holds them to it: an anchored `/models/` is reported, because it leaves `docker/models`
bare.

**Fail closed, and proven able to fail.** Finding no compose file, a mount entry the reader
cannot classify, a source it cannot reduce, or a `git` it cannot run are each a failure rather
than a pass, since a scan whose glob matched nothing would report success forever. The reader
(`scripts/composemounts.py`, split out at the line cap) refuses an inline `volumes:` list, a
mount without a `type`, a type it has not been taught, and a short-syntax entry carrying an
expansion. Before being trusted the scan was reddened twice over the real tree: a planted
`docker/docker-compose.cache.yml` with `${CORTEX_CACHE_DIR:-./hfcache}` drew two complaints
(`hfcache` and `docker/hfcache`) and exit 1, which is precisely the third case this was written
for, and deleting the `models/` line from `.gitignore` drew eight across four overrides. Both
went back to `bindcheck OK` on revert.

### Two silences the first reddening did not reach (2026-08-08)

Reddening a scan on the shapes it already reads says nothing about the shapes it walks past, and
this one walked past two that `docker compose config` resolves into live binds.

**A flush sequence.** YAML lets a list sit at the indent of its own key, and compose accepts it,
so `volumes:` at four spaces with `- type: bind` also at four is a real mount. The reader closed
a block at the first line no deeper than its key, so the entire list fell outside it and zero
mounts were read, with no error: the exact "quietly walks past the one mount a new override adds"
the module's docstring promises against. A block now ends at a line **shallower** than its key, or
at one beside the key that is not a list item.

**A flow-style entry.** `- {type: bind, source: ./x, target: /y}` is the long syntax written
inline. It reached the short-syntax reader, where `{type` is not a path prefix, so it was
classified as a named volume and skipped. Flow style is now refused by shape, opener `{` or `[`,
rather than misread, which is the reader's own contract: raise on anything it was not taught.

**And an exemption that answered for two landings at once.** Both project directories are checked,
but tracked-ness was asked once for the mount: any landing being tracked exempted the other. A
source can name an input the repo ships under one project directory and nothing at all under the
other, which is exactly what `./docker/postgres/init.sql` does (`docker/docker/postgres/init.sql`
under the `docker/` project directory), and it is the second landing a compose run creates. Both
questions are now asked per landing, and `.gitignore` gained `docker/docker/` for that phantom
nest, anchored because only the one under `docker/` is phantom.

Proven able to fail, each on a planted repo with a real `git`: the flush block draws two
complaints and exit 1, the flow mapping and the flow sequence each draw a refusal and exit 1, and
a bind whose root landing is tracked draws one complaint naming `docker/docker/seed.sql`. Each
returns to `bindcheck OK` once the landing is accounted for.

## Addendum (2026-08-09): the wrap exempts a line's kind, and the footer is not one of them

The 2026-07-19 addendum shipped one of the four exceptions and named what the other three want:
a fence toggle carried through the walk, a heuristic for a pasted command, and a decision on
whether a `BREAKING CHANGE:` footer is exempt at all or simply wrapped. All three are decided
here, and two of the three answers are not the ones that were sketched.

**The footer is not exempt. It wraps like the prose it is.** The argument is what the footer
actually is: a token read by a machine over a value that is ordinary prose. Two machines could be
reading it, and neither loses anything to a newline. Git is not one of them: git's trailer token
has no space in it, so `BREAKING CHANGE:` is not a trailer at all, and
`git interpret-trailers --parse` prints nothing for a message whose only footer is that one while
printing `Co-authored-by:` and `Signed-off-by:` from the same message shape (git 2.43.0, run
before this was written). The machine that does read it is a Conventional Commits parser, whose
specification says a footer value may contain spaces and newlines and that parsing terminates at
the next token. So wrapping preserves the whole value, and exempting the footer would carve a hole
in the wrap for exactly the class of text the wrap exists for, keyed on a token rather than on
anything about the words: a three-sentence footer would be exempt on all three sentences.

**The defect the deferral feared is smaller than the record said, which is worth stating plainly.**
Both the entry and the addendum above say the gate "can refuse a message the commit rules
themselves require". What it refuses is a footer written unwrapped, never the footer: AGENTS.md
mandates the footer and, on the same page, mandates the wrap, and the specification it cites
permits the two together. Measured rather than argued, and on the gate exactly as it stood before
this change: a footer written as one 139-character line exits 1, while the same footer wrapped
over lines of 63, 63 and 11 exits 0. There is therefore no message shape this repo's own rules
mandate that this gate cannot accept, and there never was one.

**The pasted-command heuristic is an author's mark, not a leading indent, and that is measured.**
The deferral proposed "a leading indent, a shell prompt". The indent half was tested against this
repo's own history before being built: over 433 commits, 9 body lines are indented four spaces or
more and every one of them is prose, nested bullet continuations in two messages, the one that
wired the Tauri shell and one reporting VRAM measurements per model, while fenced lines and
prompt-marked lines number 0. An indent-based exemption would
have unwrapped ordinary sentences and exempted nothing that has ever been written here, which is
the "exempts too much" failure in its purest form. What ships instead is `_PROMPT`, matching
`^\s*\$ \S`: a line whose first token is a bare `$`, which is a mark an author writes on purpose
and which prose does not carry.

**The fence is a toggle over the walk, and a fence left open is itself a violation.** Any line
whose first non-blank characters are ``` or `~~~` toggles the state, an info string (```bash)
included, and the width rule does not measure a line between an open and a close. If the walk ends
with a fence still open, `check_widths` reports the line that opened it, because the alternative is
one stray fence silently exempting every line after it, which is a gate that has stopped holding
while still exiting 0.

**The exemption is width only, and that has a measured cost.** Inside a fence and after a prompt,
the dash ban, the volatile-reference ban and the resolving-hash check still read every line. That
is deliberate, since a citation does not stop being volatile for sitting in a paste, but it means
two ordinary pastes are refused: `cargo llvm-cov -- --nocapture` draws the spaced-ASCII complaint,
and `git show` with a short hash that resolves draws the hash complaint. Both were reproduced
inside a fence rather than reasoned about, and the residue is recorded as its own deferral in the
three places this repo requires: the entry in
[docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates), its line in
[docs/refinements/index.md](../refinements/index.md) under fix-when-it-bites, and this addendum.

**What the gate still cannot see.** The fence toggle is not a CommonMark implementation: it does
not require a closing fence to match the opener's character or length, and it knows nothing of
indented code blocks, list context, or a fence nested in a fence. The prompt marks its own line and
not the output printed under it, which wants a fence. And nothing here tells a paste from prose that
merely resembles one, by design: both exemptions are author declarations, the only signal that does
not guess.

**Proven able to fail before being trusted**, running the real checker over nine message files. A
73-character prose line exits 1; the same line after a closed fence exits 1 naming line 7, which is
the leak that matters; a 104-character `docker compose` invocation exits 0 inside a fence and 0
behind a `$` prompt; an unclosed fence exits 1 naming the line that opened it; a 77-character prose
line indented four spaces under a bullet exits 1, which is the rejected heuristic held to its own
measurement; a 125-character footer exits 1 while the same one over lines of 63 and 61 exits 0;
and a fenced paste carrying a
resolving hash and a bare `--` exits 1 on both, which is the deferral above measured rather than
assumed.

## Addendum (2026-08-09, later): the paste exemption reaches the dash ban and stops there

The addendum above shipped the kind exemption as a **width** rule and recorded what that leaves
as its own deferral: inside a fence and after a `$` prompt, the dash ban, the volatile-reference
ban and the resolving-hash check still read every line, so `cargo llvm-cov -- --nocapture` and a
`git show` of a live short hash are both refused inside a paste. Which of those three a paste has
a claim on is decided here, rule by rule.

**Landed ahead of its trigger, and the trigger is named rather than glossed.** The stated trigger
was the first commit whose paste carries either shape. It has not fired: over 437 commits the
history holds 0 fenced lines and 1 prompt-marked line, that one being the `docker compose` paste in
the commit that shipped the kind exemption hours earlier, and it carries neither a bare `--` (its
dashes are all attached flags) nor any hex token at all. What moved this instead is that the wall
is now one paste away rather than hypothetical: the paste facility is in use as of that commit, and
the commands this repo would paste are its own gate invocations. Three of those carry the separator
in the `justfile` today, `cargo clippy ... -- -D warnings` twice and
`cargo test ... -- --ignored --nocapture` once, with the same shape in two runbooks. An author
pasting one of them meets exactly the choice the parent entry exists to prevent, between mangling
the paste and bypassing the hook.

**The rules split two and two, and the line between them is not "is this the author's prose".**

| rule | exempt inside a paste | why |
| --- | --- | --- |
| the 72-column wrap | yes (shipped earlier) | a paste says what it says because of where its newlines are |
| the dash ban (em, en, spaced ASCII `--`) | yes (this addendum) | the ban is on a dash used as PUNCTUATION, and verbatim text punctuates nothing |
| the volatile-reference ban | **no** | the rule is about the message still reading correctly after the thing it points at moves |
| the resolving-hash check | **no** | same, and a pasted hash goes stale on exactly the rewrite a cited one does |

**The dash ban is exempt because its subject is absent, not because a paste is inconvenient.**
ADR-0026 decision 2 bans ASCII `--` in a message on the reasoning that a commit message is pure
prose, so ` -- ` there is an em dash in ASCII clothing. Inside a paste that premise fails: the text
is not prose in any register, and `--` in `cargo llvm-cov -- --nocapture` is cargo's own argument
separator, a token of a command line with no punctuating role to play. The remedy the rule
prescribes settles it. Every rule states one, and this one's is "restructure the sentence"; a paste
has no sentence to restructure, and the only two things an author can do instead are drop the paste
or alter it, the second being precisely the "rewriting messages rather than checking them" failure
the wrap exemption was built to avoid.

**All three dash forms, not just the ASCII one.** The recorded entry offered a narrower reading,
exempting "only the argument-separator `--` and a hash inside a fence", and the narrow half of it
is refused. A rule that exempts ASCII `--` inside a paste while still banning U+2014 there is a
rule about character sets rather than about kinds, and it fails the case that motivates it: pasted
program output can carry an em dash, and an author who has to strip it is altering a paste to
satisfy a gate. The exemption is keyed on the line's kind, which is an author declaration, exactly
as the width exemption already is; making one rule read the kind and another read the character
would leave two answers to "is this a paste" in one file.

**The volatile-reference ban and the hash check are not exempt, and this is the sharper half of
the decision.** The tempting symmetry is that a paste is not the author's prose, so no prose rule
should reach it. That reading is wrong about what these two rules are for. The wrap and the dash
ban are about the text as typed, and a paste was not typed. These two are about the message's
**future**: a citation is banned because the message must still read correctly once the planning
docs move on, and a resolving hash is banned because a rewrite invalidates it. Neither of those
harms depends on who produced the characters. A pasted `git show` of a live short hash puts that
hash in the commit message, and after the next rewrite it is a command that fails, in a message
that no longer
says what it meant; the parent entry conceded as much ("a hash pasted into a body still stops
resolving after a rewrite") while proposing to exempt it anyway.

The asymmetry that closes the argument is that **these two rules keep their remedy inside a
paste**. Reflowing a command changes it, and stripping its `--` breaks it, so the wrap and the dash
ban have no remedy there. But `git show <sha>` is a paste that says everything the original said,
and a fenced grep can name a document instead of a decision number: the author loses nothing that
the paste was carrying. A rule whose remedy survives has no claim on an exemption, and a rule whose
remedy does not is where the exemption belongs. That is the whole of the boundary, and it is why
the table above splits where it does rather than by which rules happen to be annoying.

**One walk, not a second one.** `classify_lines` is the fence toggle and the prompt test lifted out
of `check_widths` into a classification of its own, returning one `Line(number, text, pasted)` per
line plus the line any unclosed fence opened. The wrap rule and the prose rules both consume it, so
there is exactly one answer in the file to where a block begins and ends; two walks would have been
two chances to disagree. Line 1 is the header, which is prose by construction (a subject cannot
open a fence) and carries its own rules, so the toggle starts below it and no message can exempt
its own subject. A fence marker counts as part of the block it delimits rather than as prose, which
is what keeps an info string out of the prose rules.

**Proven able to fail before being trusted**, running the real checker over real candidate
messages, and with the defect reproduced first on the checker exactly as it stood at the previous
commit. Under that one, a fenced `cargo llvm-cov -- --nocapture` exits 1, the same command behind a
`$` prompt exits 1, and a fenced line carrying an em dash exits 1; under the checker as it now
stands all three exit 0. **The leaks were tested rather than assumed**: the same separator with no
fence around it exits 1, the same separator on the line after the fence closes exits 1 naming line
6, the same separator on the line after a `$` prompt exits 1 (the prompt marks its own line, which
is the recorded limit held to its own measurement), and a message whose fence is never closed exits
1 naming the line that opened it, with the prose rules reporting nothing extra. **And the two rules
a paste is not exempt from still fire inside one**: a fenced `git show` of this repo's own HEAD
short hash, which really resolves, exits 1 on the hash, and a fenced `grep -n 'ADR-0026' docs/adr/*.md`
exits 1 on the decision-record number. An em dash in program output printed under a `$` prompt
rather than inside a fence exits 1, which is not a defect but the recorded limit: the prompt marks
its own line and output wants a fence.

**No new deferral opens, and that is a decision rather than an omission.** Two limits are worth
writing down beside the behaviour instead. The exemption is an author declaration, so a fence
around ordinary prose launders it past the dash ban as it already launders it past the wrap; that
is the same "nothing here tells a paste from prose that merely resembles one" this ADR already
records, and the alternative is a gate that guesses. And a paste of `git log --oneline` output is
refused, every line of it being a hash, which is the accepted cost of the column above rather than
a gap: such a paste is a message full of pointers that stop resolving, which is the case the rule
was written for. Neither has an instance in the tree, and filing either would inflate the backlog
with work nothing is waiting on.

## Addendum (2026-08-22): a sixth cross-tree scan, over one variable's several compose defaults

The compose-default survey behind the cross-language scan's 2026-08-21 widening settled that a
default no tree declares is not a coupling, `crosscheck.py` comparing a declaration against the
places restating it and there being no declaration to read. It also named the one real defect that
answer leaves standing, which is a different shape: **a variable spelled several times in compose
must carry one default in all of them, and nothing held it to that.**
`${CORTEX_PG_PASSWORD:-cortex}` is written three times in one override, once as the server's own
password and twice as a client's; `${CORTEX_MODELS_DIR:-./models}` is written in four files that
mount one host directory read-only. One spend drifting from its siblings is a stack that fails at
run time in a way nothing static reported: Postgres refusing its own clients, or one service
reading models out of a directory the others do not. `scripts/defaultcheck.py` is that check, and
it joins the line cap, the dash ban, the constant registry, the bind check and the backlog check as
an unconditional `just check` scan.

**The counts, and what they are over.** They are over every `${...}` and `$NAME` form in the ten
compose files under `docker/`, read by the gate's own reader. The survey recorded 70 substitutions
over 56 variables, of which 8 are spelled more than once. Re-derived at the commit that recorded
it, those three numbers are exact. Re-derived at this commit they are **71 over 57, still 8**: the
one-turn tool deadline landed `CORTEX_TOOLS_CALL_TIMEOUT_S` between the two readings, which is one
new substitution of one new variable and joins no group. Of the 73 total forms, 71 carry a `:-`
default and 2 carry a `:?`, both of the latter spelled once. The 8 groups hold 22 spends between
them.

**One claim in the record did not survive re-derivation.** It said `scripts/composemounts.py`
already parses these files, so the reader exists. It does not. That module reads `volumes:` blocks
and returns bind mounts; it has no notion of a substitution anywhere else in the file, which is
where every one of the three password spends and two of the four model-directory spends live. What
was reusable is the file discovery, and that is now `scripts/composefiles.py`, read by both compose
gates so neither can learn about a new override while its sibling does not. The substitution reader
is new, and it is `scripts/composedefaults.py`.

**The rule is not that all spellings are identical.** The counterexample was in the tree before the
gate was: `${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8.0}` in an environment block against
`${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8}g` in two container limits, deliberately, because docker parses
`8.0g` as a size and refuses it. So the several defaults of one variable must be the same **value**,
compared through the same `values.whole_spelling` the cross-language scan renders that pair with:
identical text is one value with nothing to reduce, and anything else must reduce and re-spell
whole, so `8.0` ties to `8` and `8.5` does not, its fraction being lost rather than zero. That
function was private to the spelling machinery and is public now, for that one caller; the
`Spelling` enum around it stays the vocabulary of a mention, which a compose default is not.

**The operator is part of the answer.** Two spends must fall back the same way as well as to the
same value. `${V:-x}` and `${V-x}` disagree about a variable set to the empty string, and `${V:?}`
beside `${V:-x}` is one file demanding what another quietly supplies. So a group's operators must
match first, and only the operators whose argument is a value at all are then compared: two `:?`
spends wording their message differently have not drifted. No group in the tree mixes operators
today, so this half of the rule is strictness bought before it is needed, which is the direction a
gate should be wrong in.

**Where it lives, and why not in `crosscheck.py`.** That scan is registry-driven. Every question it
asks starts from a hand-written entry naming a declaring site, and its documented subject is a
value some tree declares against the places restating it. This question has no registry and no
declaration; it is discovered by walking the compose files, and its far sides are each other.
Folding it in would give one scan two entry points and make its stated subject false, which every
description of the gates in this repo would then have to stop saying, and it would relitigate by
placement the very decision that these are not couplings. It sits beside `bindcheck.py` instead,
the other gate that walks every compose file and fails closed on finding none. The one-fewer-file
argument for folding was illusory anyway: `crosscheck.py` stands at 277 lines of a 300 cap, so the
fold would have forced a split on its first day.

**What the reader treats as a spend was decided rather than defaulted**, because a false positive
here fails every future commit. `$$` is compose's escape for a literal dollar and is consumed
whole, so `$${V}` spends nothing. `${V}` and `$V` are spends carrying no default, compared on their
operator alone. `${V:-}` is a real default, the empty string, and disagrees with a filled one. A
substitution inside a quoted string is read, which is the whole point: compose expands before YAML
parses, and the three password spends are inside a connection string, an environment value and a
client's variable. A **whole-line** comment is skipped, compose expanding nothing in one, which
leaves a default written there as prose and therefore the cross-language scan's question, it having
registered two compose comments already. A **trailing** `#` is deliberately not detected: this
reader has no model of YAML quoting, so it cannot tell a marker from a `#` inside a connection
string, and reading the text either way is the fail-closed side of not knowing. A `$` opening none
of those forms, a brace that never closes, a nested expansion and a name that is not an identifier
are each raised rather than skipped.

### Proven able to fail, one planted drift per group

Eight groups, eight plants, each a single edit to a real compose file in the working tree, each
followed by `cd scripts && uv run python defaultcheck.py --root ..` and a `git checkout --` whose
restoration was compared by SHA-256 digest against the file before the edit. Every one exited 1 and
named every spend of the variable, not only the edited one. The counts below are over the ten
compose files under `docker/` at this commit.

| Group (spends) | Planted edit | Result |
| --- | --- | --- |
| `CORTEX_PG_PASSWORD` (3) | the client's `PGPASSWORD` to `cortexx` | exit 1, all 3 spends named |
| `CORTEX_MODELS_DIR` (4) | the roster mount to `./model` | exit 1, all 4 spends named |
| `CORTEX_MODEL_BRAIN` (2) | the healthcheck dial to `brains` | exit 1, both spends named |
| `CORTEX_MODEL_CORTEX` (2) | the healthcheck dial to `cortexx` | exit 1, both spends named |
| `CORTEX_SUBAGENTS_CPU_BUDGET` (2) | the cgroup `cpus` to `4.5` | exit 1, both spends named |
| `CORTEX_SUBAGENTS_PARALLEL` (3) | the server flag to `3` | exit 1, all 3 spends named |
| `CORTEX_SUBAGENT_CTX_SIZE` (3) | the GPU override's env to `4096` | exit 1, all 3 spends named |
| `CORTEX_SUBAGENTS_MEM_BUDGET_GB` (3) | `memswap_limit` to `7` | exit 1, all 3 spends named |

And the converse, which is the half that matters most here, since a gate that reddens on everything
would also redden on the tree's one deliberate re-spelling:

| Case | Expected | Result |
| --- | --- | --- |
| the tree as it stands, `8.0` beside `8` twice | green | exit 0, `defaultcheck OK` |
| a third whole spelling, `8.00`, beside those two | green | exit 0, `defaultcheck OK` |
| a fraction that is lost rather than zero, `8.5` beside `8` | red | exit 1, naming all 3 spends |
| a whole-line comment restating `./cache` beside a live `./models` | green | exit 0, comment not read |
| the same text as a trailing comment on the value line | red | exit 1, that line named twice |
| a nested `${CORTEX_MODELS_DIR:-${INNER}}` | red | exit 1, the reader refusing it |
| an operator it was not taught, `${CORTEX_NGL!99}` | red | exit 1, the reader refusing it |

The suite pins both directions too, so `check-scripts` catches a drift even when
`check-defaultcheck` is not the recipe that runs: the deliberate pair is asserted green,
a real drift in that same variable is asserted red, and two guards on the guard fail if the tree
ever stops carrying six variables with a sibling to disagree with, or if the set of variables whose
defaults differ in text stops being exactly the memory budget. That last one is a set and not a
membership on purpose, so a second re-spelling landing in the tree gets argued rather than riding
in on a comparison written for the first.

**One deferral opens**, recorded in the backlog: the trailing-comment reading above is a documented
strictness with no instance in the tree, and teaching the reader enough YAML quoting to tell a real
comment from a `#` inside a scalar would let a note sit beside a value. Nothing is waiting on it,
and the remedy meanwhile is one line long.

## Addendum (2026-08-23): the trailing note stays a spend, and the reason is now measured

The compose-defaults gate landed with one strictness bought deliberately: a note written after a
value on the same line is read as a second spend of the variable it names, because the reader has
no model of YAML quoting and cannot tell a marker from a `#` inside a scalar
([R-385](../refinements/tasks/385-a-note-beside-a-compose-value-is-read-as-a-spend.md)). That entry
is **declined**. The reader goes on reading a trailing `#`, and the three things measured while
deciding are worth more than the deferral was.

**The strictness is a false positive and not a conservative reading.** Compose interpolates
neither kind of comment. `docker compose config` (v2.39.1) refuses a file whose live value spends
an unset `${CORTEX_TEST_UNSET:?...}` and accepts the same form written as a whole-line comment and
as a trailing one, and the refusal names `services.a.command.[]`, a path into the parsed document.
So interpolation runs over the strings a YAML parse produced, a comment never survives that parse,
and nothing in a note is ever spent. The gate's whole-line skip is therefore exact, and its
trailing-note reading is wrong about compose rather than careful about it.

**The remedy as the entry proposes it reddens the tree it protects.** Written out exactly as the
entry describes it (track single and double quotes across the line with the backslash escape, take
a `#` that opens a line or follows whitespace outside a quote, refuse an unterminated quote and a
block scalar) and run over the ten compose files under `docker/`, it refuses five lines in two of
them: the three block scalars at `docker-compose.tools.yml` lines 29 and 60 and
`docker-compose.subagents-roster.yml` line 32, and lines 35 and 36 of that roster file, which sit
inside a folded scalar and carry three double quotes and one. A per-line quoting model reads those
last two as a quote that never closes, which is exactly the loud refusal the entry asks for, aimed
at text this repo does contain.

**And a block scalar cannot simply be skipped, because its content is interpolated.** The same
`docker compose config` refuses a file whose `>-` scalar spends an unset variable on its second
line, naming `services.a.environment.NOTE`. So a reader that skipped block scalars would go blind
to real spends, and the roster file's own tier settings are written in one. What a correct model
needs is block-scalar tracking with indentation, reading that content for substitutions while
never reading a `#` in it as a marker: a YAML parser, in a project whose `pyproject.toml` declares
no dependencies at all, bought to allow a note beside a value.

**The asymmetry is the decision.** Reading a note as a spend is loud: the gate exits 1, names the
line twice among the group's spends, and the remedy is to move the note above the value. A `#`
wrongly read as a marker is silent: every substitution after it drops out of the comparison, and
the group goes on agreeing with itself, which is precisely the failure this gate was written to
remove. The same argument `headingshapes.py` makes for refusing six heading shapes rather than
emulating a renderer holds here with the added weight that the mechanism is measured: no compose
file in this tree wants the shape, and two of them already break the model the remedy would need.

**One narrower task opens.** The fault says nothing about the one-line remedy, and a reader who
hits it sees one `path:line` twice among the spends with no hint that a `#` is why
([R-391](../refinements/tasks/391-a-fault-that-names-one-line-twice.md)). That is the residue this
decline leaves, and it is a message rather than a reader.

### Records

The record is the task file
[R-385](../refinements/tasks/385-a-note-beside-a-compose-value-is-read-as-a-spend.md), which
closes as declined, [docs/refinements/index.md](../refinements/index.md), which is regenerated
from it, this addendum, and the two documents that state what the reader does:
`scripts/composedefaults.py`'s docstring and
[docs/modules/repo-gates.md](../modules/repo-gates.md), both of which now say the reading is
settled rather than deferred, and both of which had also been describing compose as expanding the
raw text before YAML sees it, which the first measurement above corrects.

## Addendum (2026-08-23): the compose-defaults fault now points at the note behind it

The decline that left `composedefaults.py` reading a trailing note as a spend was paid for with one
rough edge: a group containing such a note is reported by naming the same `path:line` twice, which
is true and is not the remedy
([R-391](../refinements/tasks/391-a-fault-that-names-one-line-twice.md)). `defaultcheck.py` now
appends the remedy to that fault.

### The condition is a repeated place, not a group on one line

The entry proposed "a group whose spends share one file and one line is the whole of the
condition". Replanting the note it quotes shows that is wrong: `CORTEX_MODELS_DIR` is spelled five
times across four compose files, and the note makes **two** of those five one line. A whole-group
test would have stayed green on the exact case the entry was written from. So the condition shipped
is a repeated `path:line` inside the group, which is what the quoted fault has always shown.

### The hint is a reading, not a guess

No `#` is looked for, because one variable really can be spelled twice on one line with no comment
in sight: `"${V:-a}/in:${V:-b}"` is one value spending one variable twice. The sentence therefore
names the line the spends share, which is what was measured, and offers the note as the likely
reading rather than as a finding: "which is what a note written after a value looks like to this
reader, so if one of them is a comment, move it above the line it annotates".

### Proved on the real tree, and in both directions in the suite

A note restating a stale model directory was planted beside the mount source in
`docker/docker-compose.gpu.yml`, the gate run, the file restored from a copy taken beforehand, and
the gate re-run green. The fault carried the remedy after the change and did not before it. Three
cases pin it in `scripts/tests/test_defaultcheck.py`: the planted note, a group spread over two
lines that must be offered no such remedy, and two spends on one line with no comment, which gets
the hint as the maybe it is worded as.

### Records

The record is the task file
[R-391](../refinements/tasks/391-a-fault-that-names-one-line-twice.md), which closes,
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it,
`scripts/defaultcheck.py`, which carries the hint, and this addendum.

## Addendum (2026-08-24): what the dash ban's collection is, now that it has to say

Printing how many text files the scan read made the difference between that number and the repo
visible for the first time, and the difference was not nothing. The walk read files git does not
track, all of them generated or local output, and skipped files git does track, all of them binary
assets. This decides what the collection is rather than leaving the print to imply one.

### Re-derived first, and the numbers had moved

Measured today, before anything changed, against a tree that has taken commits since the reading
that opened this. The old walk read **1262** text files over 242539 lines; git tracks **1278**
paths. The two sets are not nested, and the shape of the difference is exactly what was recorded:
**ten** files read that git does not track, the five generated Tauri schemas under
`body/app/src-tauri/gen/`, `body/coverage.json`, the three `measurements/*.json` blocks a live
measurement leaves behind and `sandbox/hello.txt`; and **twenty six** files tracked and never read,
every one a binary asset (the Tauri icon set, the logo, the overlay screenshots and the turn GIF)
that the binary skip is right to pass over. The earlier reading of 1252 and 1268 was over the same
ten and the same twenty six.

### The collection is the working tree minus what git ignores

Three candidates were weighed: the working tree, the index, and `git ls-files`.

`git ls-files` is what the repo ships, it is what the rule is about, and it is the only candidate
whose printed count is reproducible between this machine and CI. It loses anyway, on the case that
made the walk a walk. A file an agent wrote a minute ago is prose this repo is about to own, and
under `ls-files` the gate goes green on the document being written in front of it and reddens only
once somebody stages it, which is after the sentence is written and usually after it has been read.
The index is the same argument one step later: it covers the staged file and still not the new one.
An unstaged new file is the single most common way prose enters this repo, an agent writing an ADR
or a task file, and a style gate that cannot see it is a gate that arrives after the fact.

So the working tree stays, and the fix is the smaller one: **skip what git ignores.** That removes
all ten of the untracked files, none of which anybody wrote as prose, and touches no file a person
wrote. It also removes the consequence that was latent rather than theoretical: a banned dash
inside generated output was a red whose only remedy is deleting a file the repo does not ship,
which is a gate telling the truth about the wrong collection.

Git is asked **once**, `git ls-files --others --ignored --exclude-standard --directory -z`, which
costs about three milliseconds and collapses a wholly ignored directory into a single entry the
walk prunes rather than descends. That prune is worth more than the count: `models/` and `pgdata/`
are ignored bind targets that a compose run fills with GGUFs and database dumps, and the old walk
read every byte of them into memory to decide they were binary.

**A git that cannot answer is exit 2**, not a quieter scan over everything. The collection is now
defined by git's answer, so without one the printed count is over nothing anybody named, and this
is the posture `bindcheck.py` already takes toward the same dependency. The cost is real and worth
stating: `--root` must now name a git working tree, where before it named any directory.

### What this does to the two numbers, and to the floor

The walk now reads **1252** text files over 234483 lines, which is 10 files and 8056 lines of
output nobody wrote. On a clean tree that set is exactly the tracked text: 1278 tracked paths minus
the 26 binary assets is 1252, and the reading matches it to the file. The count is therefore
reproducible between this machine and CI for a clean checkout, and differs from it by exactly the
files not yet committed, which is the difference the walk exists to have.

The floor stays at one file and keeps its meaning, but the meaning now has a second road to it. It
said "a walk that read no text file cannot fail"; narrowing the walk adds a way to read none that
has nothing to do with entering the tree, which is a root where git ignores everything under it.
Both are the same fact about the collection being empty, so one floor covers both and a test now
pins the new road.

`SKIPPED_DIRS` stays as it is, and is now partly redundant on purpose. `.git` is the one entry git
does not call ignored, so the list cannot become git's answer alone; the rest name trees this
repo's own `.gitignore` also covers. They stay because two other modules read that list,
`linecap.py` through the suite that holds the two to each other and `backloganchors.py` directly,
so the three walks skip one set of names rather than three.

### Proved able to fail, five times, over the scripts suite

Five planted mutations over `scripts/dashcheck.py` (the `scripts/tests` suite, 852 tests after this
change, which is the collection every count below is out of). Each was restored from a copy taken
before the first, with `__pycache__` purged between runs, and the 852-passed baseline was
re-established after the last.

| # | mutation | expected | observed |
| --- | --- | --- | --- |
| 1 | the ignore consult dropped, the walk reading everything again | the collection tests fail | 6 failed, 846 passed |
| 2 | ignored files skipped, ignored directories still descended into | the prune test fails | 2 failed, 850 passed |
| 3 | a git that cannot answer treated as nothing ignored | both refusals fail | 2 failed, 850 passed |
| 4 | the trailing slash left on, so a directory entry never matches a name | the prune test fails | 2 failed, 850 passed |
| 5 | the floor lowered to zero | both floor tests fail, the new road included | 2 failed, 850 passed |

Row 3 is the row the fail-closed decision needed: reading everything on a git failure is the
tempting alternative, it hides no violation, and it silently restores the exact reds this change
removes. Row 5 is the check that the floor still means what it meant, its second failure being the
tree git ignores entirely, which could not have existed before this change.

### What this opened

Two hand-kept things did not notice that git can now be asked. The gates keep the environment strip
that makes a git call inside a hook answer about the right repository in three separate modules, and
a fourth caller will write a fourth copy
([R-419](../refinements/tasks/419-the-git-call-inside-a-hook-is-written-three-times.md)). And
`SKIPPED_DIRS` is a hand-written list of directory names that `.gitignore` already covers for all
but one entry, read by three walks
([R-420](../refinements/tasks/420-the-skipped-dirs-list-restates-what-git-ignores.md)).

### Records

The record is the task file
[R-411](../refinements/tasks/411-the-dash-ban-reads-a-working-tree-not-a-commit.md), whose origin
line pointed at the wrong decision record and now points here,
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it,
`scripts/dashcheck.py`, which asks git and states the collection in its own docstring,
`scripts/tests/test_dashcheck.py`, which walks a real git working tree for the reason
`test_bindcheck.py` does, [modules/repo-gates.md](../modules/repo-gates.md), which states what the
gate now reads and what it now refuses, and this addendum.

## Addendum (2026-08-24, later): the environment a gate's git call runs with has one home

Three gates here ask git something and each rebuilt the same environment before doing it. The
copies were correct, which is the problem: the fourth caller writes a fifth, and the one that
forgets is not red anywhere.

### Re-derived first, and the count was low

The strip was written out **six** times, not the five the record that opened this counted: three
gates (`bindcheck.py` asking whether a path is tracked and whether it is ignored, `commitlint.py`
whether a token resolves to a commit, `dashcheck.py` which paths git ignores) and **three** suites,
`test_bindcheck.py`, `test_commitlint.py` and `test_dashcheck.py`, each with a fixture that drives
a real git against a temporary repository. Every one of the six carried its own comment saying why,
in its own words.

### The environment is shared and the call is not

The record that opened this argued the environment alone, and reading the three call sites confirms
it. They disagree about every part of a call except the environment: `check-ignore` answers 1 for a
legitimate no while a non-zero from `ls-files` is a failure; `bindcheck.py` raises `BindCheckError`
and `dashcheck.py` raises `IgnoreQueryError`, each named for the question it could not answer;
and `commitlint.py` answers an `OSError` with False rather than an exception, because a box with no
git cannot disprove a hash and blocking a commit over that would be the wrong trade in a commit-msg
hook. A shared runner would therefore take an allowed-codes set, an exception factory and an
`OSError` policy, which is one parameter per caller and a switch statement wearing a function's
clothes. The environment is one fact with one reason, so `scripts/gitenv.py` is one constant and
one function, and each gate keeps its own argv and its own reading of the answer.

`GIT_PREFIX` ends in its underscore on purpose. Dropping everything that starts `GIT` would take
`GITHUB_ACTIONS` and the rest of a runner's environment with it, which is a different bug in the
same line.

### The fixtures read it too

A fixture that rebuilds the environment by hand can drift from the gate it tests, and the drift is
invisible in exactly the way the original defect is: the fixture's `add` lands in the in-flight
commit's index rather than the temporary repository's, and the suite reports a failure about
something else entirely. So the three suites import the same function. What stays written out in
each of them is the literal `GIT_` in the assertion that the strip happened, because a test that
read the prefix from the module would agree with whatever the module now means.

### Proved able to fail, six times, over the scripts suite

Six planted mutations over `scripts/gitenv.py` and its three call sites (the `scripts/tests`
suite, 859 tests after this change, which is the collection every count below is out of). Each was
restored from a copy taken before the first, with `__pycache__` purged between runs, and the
859-passed baseline was re-established after the last.

| # | mutation | expected | observed |
| --- | --- | --- | --- |
| 1 | the strip removed, the helper returning the environment whole | every end-to-end test fails, and the drop test with them | 4 failed, 855 passed |
| 2 | the prefix widened to `GIT`, taking a runner's own variables | the survival test fails | 1 failed, 858 passed |
| 3 | `dashcheck.py` alone forgets the helper, inheriting the ambient environment | its end-to-end test fails, and the obligation test with it | 2 failed, 857 passed |
| 4 | `bindcheck.py` alone forgets it | the same pair, for that gate | 2 failed, 857 passed |
| 5 | `commitlint.py` alone forgets it | the same pair, for that gate | 2 failed, 857 passed |
| 6 | `bindcheck.py` writes the strip out again itself, correctly | only the obligation test fails | 1 failed, 858 passed |

Rows 3 to 5 are the rows this close needed, and they are why the three end-to-end tests exist at
all. A helper nobody is obliged to call is not a fix, so each gate is held to calling it by a test
that exports a `GIT_DIR` naming no repository at all over a real `git` and demands the right answer
anyway: without the strip, `bindcheck.py` reddens on a clean tree, `dashcheck.py` exits 2 on one,
and `commitlint.py` stops reporting a hash that really resolves. Row 1 is the same three tests plus
the unit one, which is the shape a shared fact should fail in.

Row 6 is the one that pays for the last test, and it is the trigger this entry was opened with: a
caller that writes a correct copy is invisible to every behaviour test here, since the behaviour is
identical, and it is the copy that goes stale. So a file in this tree spelling a git argv is held
to spelling the call that hands it an environment, which is the obligation a fourth caller inherits
without being told.

### Records

The record is the task file
[R-419](../refinements/tasks/419-the-git-call-inside-a-hook-is-written-three-times.md),
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it,
`scripts/gitenv.py` and `scripts/tests/test_gitenv.py`, the three gates and the three suites that
now read it, [modules/repo-gates.md](../modules/repo-gates.md), and this addendum.

## Addendum (2026-08-24, later still): the skip list is not `.gitignore`, and now has one home

Teaching the dash ban to ask git what it ignores left a hand-written list of directory names
beside the answer, most of which git already knew. The question was whether the list should
survive. It should, for two names out of ten, and the four copies of it were the real defect.

### Re-derived first, and two of the three claims had moved

- **The overlap is eight of ten, not nine.** Measured today with the machine's own excludes file
  taken out of the question, git ignores `.venv`, `.claude`, `target`, `node_modules`,
  `__pycache__`, `.pytest_cache`, `.ruff_cache` and `dist` wherever they appear. `.git` it never
  calls ignored, not being part of the work tree, and **`coverage` is ignored only under
  `body/app/`**, by that tree's own `.gitignore`. A `coverage/` at the root or under `brain/` is
  ignored by nothing, so the list has two real entries and eight restatements.
- **The anchor scan did not import the list; it carried a copy.** The record that opened this said
  `backloganchors.py` reads the dash ban's list directly, and the addendum above says the same. It
  did not: it had a hand-written twin of the same ten names, held to nothing. The drift this entry
  was opened to prevent was already in the tree on the day it was written.
- **Four walks, not three, and four lists.** `composefiles.py` prunes with a list of its own, eight
  names, missing the two tool caches, and its docstring argued for staying independent.

### The fork, decided: the other three walks do not learn to ask git

Collapsing the list to `.git` and letting `.gitignore` name every skipped tree loses two things,
and the first is not the redundancy anybody assumed. **`coverage` is not a restatement.** The name
joined this list as the overlay's own build output (the ADR-0011 line-cap addendum), and the repo
ignores it in exactly one place, `body/app/`, where that build output lands. A walk that skipped
only what git ignores would read a `coverage/` anywhere else, and a generated report is the kind
of file whose banned dash is a red with no remedy but deleting it, which is the red the dash ban's
collection change was made to remove.

**And it would narrow who can run `just check`.** The dash ban already refuses a root git cannot
answer about, and that is right for it, because its rule is about the text this repo owns and its
collection is git's answer. The line cap, the anchor scan and the compose walk have no rule that
mentions the repository: a cap on file length, a heading a pointer aims at, and a compose file's
binds are all true of a tree somebody unpacked from an archive. Making three more gates refuse a
directory that is not a git working tree is a real cost, paid to remove eight names that cost
nothing and are pruned before any question is asked, which is also what keeps a walk out of an
ignored bind target rather than merely quiet about it.

### What landed instead, which is the other close this entry offered

`scripts/skippeddirs.py` holds the ten names and the argument above, and all four walks read it.
`linecap.py` composes its own list from it, `SHARED_SKIPS | {"tests", "_generated"}`, so the
relationship a test used to hold is now one the code states; that test is deleted rather than kept
as a tautology, the twelve names being pinned by behaviour anyway in the walk test beside it.
`composefiles.py` joins as well, its eight names having no argument for being eight: the two
caches it lacked are trees no gate reads either way, and the two compose gates' readings are
identical across the change, 11 binds over 10 compose files and 22 landings, 8 variables over the
same 10 files and 59 read.

The claim the list makes about `.gitignore` is now measured rather than believed. A test asks git
about each of the ten, in a directory git tracks and under the repo's own ignore rules alone, and
holds the partition: eight restatements, and `.git` and `coverage` outside them. It reddens in
both directions, which is the point of comparing two things nothing compared before.

### Proved able to fail, six times, over the scripts suite

Six planted mutations over `scripts/skippeddirs.py`, its readers and the repo's own `.gitignore`
(the `scripts/tests` suite, 860 tests after this change, which is the collection every count below
is out of). Each was restored from a copy taken before the first, with `__pycache__` purged
between runs, and the 860-passed baseline was re-established after the last.

| # | mutation | expected | observed |
| --- | --- | --- | --- |
| 1 | `coverage` dropped as redundant, the assumption this entry arrived with | the overlap test fails, and the cap's walk with it | 2 failed, 858 passed |
| 2 | `.git` dropped, the entry's one acknowledged real name | the overlap test and the walks that would then read a repository | 9 failed, 851 passed |
| 3 | the list collapsed to `.git` alone, the branch declined above | the walks stop skipping anything else | 17 failed, 843 passed |
| 4 | the anchor scan keeps a correct copy of its own again | only the one-home test fails | 1 failed, 859 passed |
| 5 | the cap loses its two extra names | the four cases that are the cap's alone fail | 4 failed, 856 passed |
| 6 | `coverage/` added to the repo's own `.gitignore` | the overlap test fails from the other side | 1 failed, 859 passed |

Row 4 is the historical defect replayed: a copy that agrees with the original is invisible to
every behaviour test in the tree, which is how the anchor scan's twin lived here unnoticed, and
only an obligation on the walk itself catches it. Row 6 is the row that proves the overlap test
reads git rather than a second copy of the answer: adding a rule this repo does not have turns
`coverage` into a restatement and the partition reddens on the spot.

### Records

The record is the task file
[R-420](../refinements/tasks/420-the-skipped-dirs-list-restates-what-git-ignores.md),
[docs/refinements/index.md](../refinements/index.md), which is regenerated from it,
`scripts/skippeddirs.py` and `scripts/tests/test_skippeddirs.py`, the four walks that read it,
[modules/repo-gates.md](../modules/repo-gates.md), which states the relationship the deleted test
used to, and this addendum.
