# A name a roster borrows cannot be told from a name it claims

**Status:** declined 2026-09-12
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-26 by the close of
[R-448](448-the-module-listing-is-held-whole-and-not-in-halves.md), which split one paragraph of
[modules/repo-gates.md](../../modules/repo-gates.md) into two rosters and had to let one of them
carry names belonging to the other.

The second half of that listing groups the libraries by the gate that reads them, and it names that
gate with a name the first half owns: `bindcheck.py` reads `composemounts.py` for the mounts a
compose file declares, `samplecheck.py` reads `logsamples.py` and `logcalls.py` and three more.
Twelve such names stand there today, eleven of them opening one of the half's eleven bullets. A
roster may therefore declare the sibling set whose names its passage is allowed to carry, and every
name in that set is accepted wherever it falls in the passage.

What that cannot see is the difference between `bindcheck.py` reads `composemounts.py` and
`composemounts.py` reads `bindcheck.py`. Both sentences name the same two modules and only one of
them is true. The gate reads either one as a library described beside a reference and passes it.

The exposure is bounded and the bound is worth stating: a CLI module written into the second half
as a claim is still a member of the first half, which reports it as a member nobody named. So the
failure that survives is a sentence that reads wrongly about a module the other half already
accounts for, never a set that has silently drifted.

**Why it was left.** Telling a reference from a claim means reading the grammar of the sentence,
which is a different kind of reader from anything in this tree: every reader here answers what a
document names, and none answers what it says.

**Why it is declined.** The rule this entry ended up proposing was measured against the page and
rejects a true sentence. That rule is positional: a borrowed name is accepted only as a bullet's
first code span, since the rewrite that inverted the original proposal left every bullet opening
with the gate whose libraries it then names. On 2026-09-09 all eleven borrowed names were their
bullet's first code span and the rule was green. Two days later a twelfth arrived that is not:
the envelope bullet now reads `envelopefloor.py` reads `envelopesamples.py` and `envelopejudges.py`,
then `envelopepairs.py` reads the same format through `envelopesamples.py`, which is one bullet
about the two gates that share one library. Every word of it is true and the positional rule reports
it.

So the rule is not narrow enough to be honest, and widening it means reading the grammar, which is
the reader this tree does not have. What stays instead is the bound above, now argued rather than
assumed: the set is held twice, by membership in both halves, and the residue is one sentence's
direction about a module both halves already account for. A page describing two gates in one bullet
is better prose than a page split to suit a positional rule, which is the other thing the rule would
have cost.

## Trail

- 2026-08-26: opened by the close of
  [R-448](448-the-module-listing-is-held-whole-and-not-in-halves.md), whose borrowed-name
  allowance is what makes the hole. Recorded under what the ADR-0029 addendum on holding that
  listing in halves defers.
- 2026-09-08: trigger checked and not fired, and the entry repaired, because the listing it
  describes was rewritten after it was written. Every reading direction on the page is right:
  each of the eleven bullets opens with a gate that really imports the libraries the bullet names,
  read off the `import` statements of the eleven modules, and no module in the no-CLI half imports
  any of the eleven. So no sentence in the borrowing half is wrong today.
- 2026-09-08: what the repair corrects. The entry quoted the listing as a running paragraph
  written library first, `composemounts.py` is `bindcheck.py`'s mount reader and the two sides
  `samplecheck.py` holds together. That paragraph is gone; the half is now a bulleted list written
  gate first, `bindcheck.py` reads `composemounts.py` for the mounts a compose file declares.
  Neither quoted sentence is in the document, and the possessive-marker argument in **Why it was
  left** was about a shape the page no longer has, so both are removed. The count moved too:
  `scripts/` held 48 modules with 14 command lines when this was opened and holds 68 with 18 now,
  and the borrowed names in the passage went from seven to eleven, `envelopefloor.py`,
  `flagcheck.py`, `stubcheck.py` and `switchtail.py` being the four that arrived.
- 2026-09-08: the rewrite also inverted the remedy, which is why **What would close it** changed.
  The old proposal was to accept a borrowed name only where it is not the subject of the clause it
  opens; under the current listing every one of the eleven is exactly that, so the proposal would
  reject the whole passage. Reading the passage bullet by bullet says the inverse rule is green:
  all eleven borrowed names are their bullet's first code span, no borrowed name appears anywhere
  else in a bullet, and no member of the half opens one. That rule would report the reversed
  bullet, since reversing it moves the borrowed name out of the first position. Left open and not
  actionable, because writing the rule is a gate change owing a mutation table, and the entry's
  own alternative, arguing that the existing bound is far enough, is still unanswered.
- 2026-09-09: trigger checked and not fired again, over a listing that has grown since. The
  borrowing half still runs to eleven bullets and eleven borrowed names, each one its bullet's
  first code span, and no bullet carries a borrowed name anywhere else, read by matching every
  code span in the passage against the eighteen names the no-CLI half's sibling roster owns. The
  inverse rule this entry proposes would therefore still pass the whole passage. One count was
  wrong: the trailing paragraph names five shared modules and not three, `composefiles.py`,
  `gitenv.py`, `treewalk.py`, `skippeddirs.py` and `gatecalls.py`, and it still carries no
  borrowed name.
- 2026-09-12: declined, because the reading that was green three days ago is red, and on true
  prose. Re-derived over the current page: the borrowing half runs to eleven bullets carrying
  twelve borrowed names, and one of them, `envelopepairs.py` in the envelope bullet, is not its
  bullet's first code span. The sentence is right, `envelopepairs.py` importing
  `envelopesamples.py` and carrying a command line of its own, so the positional rule would report
  a page that says what the tree does. Both halves' membership still holds whole, 19 names in the
  CLI roster and 54 in this one, all 54 named in the passage and nothing named that is not a
  member. The other counts moved as well: `scripts/` holds 73 modules where this entry last read
  68, and the trailing shared paragraph names six modules and not five, `markdownfences.py` having
  arrived, and it still carries no borrowed name. Recorded in the ADR-0029 borrowed-name addendum,
  which also states the decline in
  [modules/repo-gates.md](../../modules/repo-gates.md) beside the allowance it is about.
