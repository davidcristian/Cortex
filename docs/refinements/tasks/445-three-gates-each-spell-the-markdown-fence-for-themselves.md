# Three gates each spell the markdown fence for themselves

**Status:** landed 2026-09-12
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-26 by the close of
[R-438](438-a-documented-log-sample-can-still-print-the-wrong-fields.md), which added the third
copy.

Three modules in `scripts/` each answer "is this line a fence?" for themselves, with the same
pattern written out three times: `headingshapes.FENCE`, which is how `backlogcheck.py` keeps a
`#` inside a code block from being read as a heading; `commitlint._FENCE`, which is how a pasted
block in a commit body escapes the wrap rule and the dash ban; and now `logsamples.FENCE`, which is
how a rendered log line is told from prose about one. All three are the same regular expression,
an optional indent in front of either of the two markers markdown accepts, and all three mean the
same thing by it.

This repo already holds that a question several gates ask should be answered once:
`scripts/composefiles.py` exists precisely so the three compose gates cannot drift apart about
which files they walk, and `scripts/skippeddirs.py` for which directories no walk enters. A fence
is the same shape of question and has three answers.

Nothing is wrong today: the three patterns are identical, and the suite for each gate holds its
own reader. What a shared module would buy is that they stay identical, and that the next reader
of markdown here starts from an answer rather than from a fourth copy.

One reader has since started from this entry instead. `rosternames.py` reads a roster out of a
passage that may contain a fenced block, and its module doc says fences are not read there because
doing so "would add a fourth markdown-fence parser to this tree, which the backlog records as
something to unify rather than to grow". So the cost of three copies is already being paid by a
reader that declined to answer the question at all, and priced its own behaviour against this
entry.

**Why it was left.** The close that added the third copy was about log samples, and extracting a
shared markdown reader means editing `commitlint.py` and `headingshapes.py`, two gates that close
had no business touching, in the same commit as a new scan. With three copies rather than two, the extraction is worth
doing and worth doing on its own.

**What would close it.** Either a `scripts/markdown.py` (or a name designed for it) holding the
fence token, with all three gates reading it and each suite still holding its own behaviour, or a
written argument that a fence is cheap enough to spell per reader and that the three are
independent by design rather than by accident.

**Landed 2026-09-12 ahead of its trigger, as the first of those two**
([ADR-0026 one-home addendum](../../adr/ADR-0026-prose-style-gates.md)). Its trigger was a fenced
block one gate read and another did not, or a fourth reader arriving. **Neither had happened, and
that is reported rather than glossed:** the three patterns were character for character
`r"^\s*(?:```|~~~)"` on the day this landed, and no fourth reader had arrived, so what moved it is
the argument the entry was written on, that three copies stay identical by inspection and nothing
reports the day one of them stops.

**What it became.** `scripts/markdownfences.py` holds the markers, the pattern built from them and
`is_fence(line)`, which the three gates call. The name is not the `markdown.py` proposed above: a
module under `scripts/` is on `sys.path` for every gate that runs there, so a file called
`markdown.py` would shadow any installed package of that name, and the tree already names a module
for its subject rather than its format (`dockerfilevolumes.py`, `protocomments.py`). The reading is
unchanged, an indent of any width in front of either marker and an info string after it, so no gate
moved: the log-sample gate reads the same 14 samples in 12 runbooks, and the backlog gate lands
every fragment over the same 642 tasks it read before the two entries below were written.

**The second half is what keeps the first from being copied again.** `spelled(module)` returns
every line where a fence marker is written into a module's code, read out of the syntax the way
`gatecalls.py` reads a call, with a marker inside a docstring passed over as prose about a fence.
The obligation beside it compares the set of modules that spell one against `{markdownfences.py}`
as an equality, so a fourth copy fails and so does a reader that finds nothing at all. This entry's
own evidence was retired with it: `rosternames.py` no longer prices its declination against a
backlog entry, and says instead that the repo map is a roster written inside a fenced block, so a
reader that stripped fences would lose that roster's boundary and every name in it.

## Trail

- 2026-08-26: opened by the close of
  [R-438](438-a-documented-log-sample-can-still-print-the-wrong-fields.md), whose new doc reader
  is the third copy. Recorded under what the ADR-0009 sample-membership addendum defers.
- 2026-09-07: trigger checked and not fired, on both halves. No fourth reader has arrived:
  `scripts/` still holds exactly three fence patterns, `headingshapes.FENCE`, `commitlint._FENCE`
  and `logsamples.FENCE`, and a search of the tree for the fence markers finds no other module
  answering the question for itself. And no fenced block one gate reads and another does not,
  because all three patterns are still character for character `r"^\s*(?:```|~~~)"`, so they agree
  on the indent they allow, on both markers, and on treating an info string as part of the fence.
  The clause is checkable in one search and can come out false, so it stays as written. Left open:
  what the entry asks for is still that the three stay identical by construction rather than by
  inspection, and nothing about today's reading changes that argument either way.
- 2026-09-09: counted again across all of `scripts/`, since the scan roster has grown to eleven
  and a new gate is where a fourth copy would appear. Still three, still character for character
  `r"^\s*(?:```|~~~)"`, and none of the readers added since answers the question for itself:
  `backloganchors.py` imports `headingshapes`, `rostermembers.py` reads the directory rather than
  the page and so meets no fence at all, and `rosternames.py`, which does read a page whose
  passages carry fenced blocks, declines to read fences and names this entry as the reason. That declination is added to the body above, because it is the strongest evidence
  the entry has and it was not written down.
- 2026-09-12: landed ahead of its trigger. `scripts/markdownfences.py` holds what a fence is, the
  three gates call it, and `spelled(module)` plus the obligation beside it hold `scripts/` to one
  spelling, read out of each module's syntax rather than out of a list of readers. No gate's
  answers moved. Recorded at the
  [ADR-0026 one-home addendum](../../adr/ADR-0026-prose-style-gates.md), with a five-row mutation
  table over the 1793-test scripts suite and one planted failure per gate on a real document. It
  opened [R-643](643-a-fence-marker-opening-a-line-inside-another-block-toggles-every-reader.md),
  the nesting rule the shared reading still does not have, and
  [R-644](644-the-fence-obligation-stops-at-the-suites.md), the set the obligation is compared
  over.
