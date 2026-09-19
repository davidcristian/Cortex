# A name a list borrows cannot be told from a name it claims

**Status:** declined 2026-09-12
**Area:** repo-checks
**Origin:** [ADR-0044](../../adr/ADR-0044-document-rosters.md)

The second half of the module listing in [modules/repo-checks.md](../../modules/repo-checks.md)
groups the libraries by the check that reads them, and it names that check with a name the first
half owns: `bindcheck.py` reads `composemounts.py` for the mounts a compose file declares,
`samplecheck.py` reads `logsamples.py` and `logcalls.py` and three more. Twelve such names stand
there, eleven of them opening one of the half's eleven bullets. A list may therefore declare the
sibling set whose names its passage is allowed to contain, and every name in that set is accepted
wherever it falls.

What that cannot see is the difference between `bindcheck.py` reads `composemounts.py` and
`composemounts.py` reads `bindcheck.py`. Both sentences name the same two modules and only one is
true. The check reads either one as a library described beside a reference and passes it.

The exposure is bounded: a command-line module written into the second half as a claim is still a
member of the first half, which reports it as a member nobody named. So the failure that survives
is a sentence that reads wrongly about a module the other half already accounts for, never a set
that has quietly come apart. Telling a reference from a claim means reading the grammar of the
sentence, which is a different kind of reader from anything in this tree: every reader here answers
what a document names, and none answers what it says.

## History

- 2026-08-26: opened by the close of
  [R-448](448-the-module-listing-is-held-whole-and-not-in-halves.md), whose borrowed-name allowance
  is what makes the hole. Recorded as a limit ADR-0044 leaves open.
- 2026-09-08: trigger checked and not fired, and the entry repaired, because the listing it
  describes was rewritten after it was written. Every reading direction on the page is right: each
  of the eleven bullets opens with a check that really imports the libraries the bullet names, read
  off the `import` statements of the eleven modules, and no module in the no-CLI half imports any
  of the eleven.
- 2026-09-08: what the repair corrects. The entry quoted the listing as a running paragraph written
  library first. That paragraph is gone; the half is now a bulleted list written check first.
  Neither quoted sentence is in the document, and the argument in the old "Why it was left" was
  about a shape the page no longer has, so both are removed. The counts moved too: `scripts/` had
  48 modules with 14 command lines when this was opened and has 68 with 18 now, and the borrowed
  names in the passage went from seven to eleven.
- 2026-09-08: the rewrite also inverted the remedy. The old proposal was to accept a borrowed name
  only where it is not the subject of the clause it opens; under the current listing every one of
  the eleven is exactly that, so the proposal would reject the whole passage. Reading the passage
  bullet by bullet says the inverse rule passes: all eleven borrowed names are their bullet's first
  code span, no borrowed name appears anywhere else in a bullet, and no member of the half opens
  one. Left open and not actionable, because writing the rule is a check change owing a mutation
  table.
- 2026-09-09: trigger checked and not fired again, over a listing that has grown since. The
  borrowing half still runs to eleven bullets and eleven borrowed names, each its bullet's first
  code span, read by matching every code span in the passage against the eighteen names the no-CLI
  half's sibling list owns. One count was wrong: the trailing paragraph names five shared modules
  and not three, `composefiles.py`, `gitenv.py`, `treewalk.py`, `skippeddirs.py` and
  `gatecalls.py`, and it still has no borrowed name.
- 2026-09-12: declined, because the reading that passed three days ago fails, and on true prose.
  Read again over the current page: the borrowing half runs to eleven bullets with twelve borrowed
  names, and one of them, `envelopepairs.py` in the envelope bullet, is not its bullet's first code
  span. The sentence is right, `envelopepairs.py` importing `envelopesamples.py` and having a
  command line of its own, so the positional rule would report a page that says what the tree does.
  Widening it means reading the grammar, which is the reader this tree does not have. What stays
  instead is the bound above, now argued rather than assumed: the set is checked twice, by
  membership in both halves, and the residue is one sentence's direction about a module both halves
  already account for. A page describing two checks in one bullet is better prose than a page split
  to suit a positional rule. Both halves' membership still holds whole, 19 names in the
  command-line list and 54 in this one, all 54 named in the passage and nothing named that is not a
  member. `scripts/` has 73 modules where this entry last read 68, and the trailing shared
  paragraph names six modules and not five, `markdownfences.py` having arrived. Recorded in
  ADR-0044, which also states the decline in
  [modules/repo-checks.md](../../modules/repo-checks.md) beside the allowance it is about.
