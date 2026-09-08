# A name a roster borrows cannot be told from a name it claims

**Status:** open, fix when it bites
**Trigger:** a bullet in the borrowing half states a reading direction the tree does not have,
naming a library as the reader of the gate that reads it. Both names are ones the passage accepts,
so the gate passes the bullet and only a person reading the sentence catches it. Checking it means
comparing each bullet against what the module it opens with imports.
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-26 by the close of
[R-448](448-the-module-listing-is-held-whole-and-not-in-halves.md), which split one paragraph of
[modules/repo-gates.md](../../modules/repo-gates.md) into two rosters and had to let one of them
carry names belonging to the other.

The second half of that listing groups the libraries by the gate that reads them, and it names that
gate with a name the first half owns: `bindcheck.py` reads `composemounts.py` for the mounts a
compose file declares, `samplecheck.py` reads `logsamples.py` and `logcalls.py` and three more.
Eleven such names stand there today, one opening each of the half's eleven bullets. A roster may
therefore declare the sibling set whose names its passage is allowed to carry, and every name in
that set is accepted wherever it falls in the passage.

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

**What would close it.** Either a rule narrow enough to be honest, or a written argument that the
bound above is the right place to stop, since the half that matters is already held twice and the
residue is prose quality rather than drift. The listing has since been rewritten into a shape one
such rule can read. Every bullet in the half now opens with the gate's name and names that gate's
libraries after it, so the rule is that a borrowed name is accepted only as a bullet's first code
span, and a borrowed name anywhere else in a bullet is a claim about a library rather than a
reference to its reader. That is the inverse of the rule this entry first proposed, which would
now reject all eleven bullets, and it is the inversion the rewrite caused. It leaves the trailing
paragraph on the three shared modules unheld, that one being prose rather than bullets, which is
tolerable while it carries no borrowed name.

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
