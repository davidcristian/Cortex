# Three checks each define the markdown fence for themselves

**Status:** done 2026-09-12
**Area:** repo-checks
**Origin:** [ADR-0062](../../adr/ADR-0062-shared-check-readers.md)

Three modules in `scripts/` each answered "is this line a fence?" for themselves, with the same
pattern written out three times: `headingshapes.FENCE`, which is how `backlogcheck.py` keeps a `#`
inside a code block from being read as a heading; `commitlint._FENCE`, which is how a pasted block
in a commit body escapes the wrap rule and the dash ban; and `logsamples.FENCE`, which is how a
rendered log line is told from prose about one. All three were the same regular expression, an
optional indent in front of either of the two markers markdown accepts.

This repo already holds that a question several checks ask should be answered once:
`scripts/composefiles.py` exists so the three compose checks cannot disagree about which files they
walk, and `scripts/skippeddirs.py` for which directories no walk enters. Nothing was wrong: the
three patterns were identical and each suite covered its own reader. What a shared module buys is
that they stay identical.

One reader had started from this entry instead. `rosternames.py` reads a list out of a passage that
may contain a fenced block, and its module doc said fences are not read there because doing so
would add a fourth fence parser to a tree the backlog records as something to unify. So the cost of
three copies was already being paid by a reader that declined to answer the question at all.

## History

- 2026-08-26: opened by the close of
  [R-438](438-a-documented-log-sample-can-still-print-the-wrong-fields.md), whose new document
  reader is the third copy. Filed against ADR-0045.
- 2026-09-07: trigger checked and not fired, on both halves. No fourth reader has arrived, and no
  fenced block one check reads and another does not, because all three patterns are still character
  for character `r"^\s*(?:```|~~~)"`.
- 2026-09-09: counted again across all of `scripts/`, since the scan list has grown to eleven and a
  new check is where a fourth copy would appear. Still three, still identical, and none of the
  readers added since answers the question for itself: `backloganchors.py` imports
  `headingshapes`, `rostermembers.py` reads the directory rather than the page, and
  `rosternames.py`, which does read a page with fenced blocks, declines to read fences and names
  this entry as the reason. That declination is added above, because it is the strongest evidence
  this entry has.
- 2026-09-12: closed ahead of its trigger, as the first of the two options
  ([ADR-0062](../../adr/ADR-0062-shared-check-readers.md), decision 6). The trigger was a fenced
  block one check read and another did not, or a fourth reader arriving. Neither had happened, and
  that is reported rather than glossed: the three patterns were character for character
  `r"^\s*(?:```|~~~)"` on the day this was done, so what moved it is the argument the entry was
  written on, that three copies stay identical by inspection and nothing reports the day one of
  them stops. `scripts/markdownfences.py` holds the markers, the pattern built from them and
  `is_fence(line)`, which the three checks call. The name is not the `markdown.py` proposed here: a
  module under `scripts/` is on `sys.path` for every check that runs there, so a file called
  `markdown.py` would shadow any installed package of that name, and the tree already names a
  module for its subject rather than its format. The reading is unchanged, so no check moved: the
  log-sample check reads the same 14 samples in 12 runbooks, and the backlog check resolves every
  fragment over the same 642 tasks. The second half is what keeps the first from being copied
  again: `marker_lines(module)` returns every line where a fence marker is written into a module's code,
  read out of the syntax the way `scriptcalls.py` reads a call, with a marker inside a docstring
  passed over as prose about a fence. The obligation beside it compares the set of modules that
  contain one with `{markdownfences.py}` as an equality, so a fourth copy fails and so does a
  reader that finds nothing at all. This entry's own evidence was retired with it:
  `rosternames.py` no longer prices its declination against a backlog entry, and says instead that
  the repo map is a list written inside a fenced block, so a reader that stripped fences would lose
  that list's boundary and every name in it. Five planted mutations over the 1793-test scripts
  suite and one planted failure per check on a real document. It opened
  [R-643](643-a-fence-marker-opening-a-line-inside-another-block-toggles-every-reader.md), the
  nesting rule the shared reading still does not have, and
  [R-644](644-the-fence-obligation-stops-at-the-suites.md), the set the obligation is compared over.
