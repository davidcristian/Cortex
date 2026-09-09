# Three gates each spell the markdown fence for themselves

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-09
**Trigger:** A fenced block one gate reads and another does not, or a fourth reader arriving.

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
