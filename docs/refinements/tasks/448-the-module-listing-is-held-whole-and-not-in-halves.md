# The gate tree's module listing is held whole, so neither of its halves is

**Status:** open, fix when it bites
**Trigger:** a module gains or loses a CLI and is left in the wrong half of the sentence, or the
count in front of the second half stops matching it, which is when a reader is told a module is
something it is not.
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-26 by the close of
[R-413](413-the-module-contracts-part-list-is-held-by-nobody.md), which registered the Public
contract paragraph of [modules/repo-gates.md](../../modules/repo-gates.md) as a roster over every
module in `scripts/`.

That paragraph makes three claims and one of them is now held. It names every module, which is
held. It sorts them into the ones with a CLI of their own and the ones without, which is not: the
roster is the paragraph, so a module named in the wrong clause passes, and a module that gains a
CLI and stays in the second list reads as a library to anyone who trusts the sentence. And it
opens the second list with a count in words, thirty four at the time of writing, which is a hand
count under the standing decision that a document's tallies are its own business.

The CLI half is machine-readable in a way the count is not: a module here has a CLI exactly when
it carries a `if __name__ == "__main__":` guard, which is one grep over the same directory the
roster already reads.

**Why it was left.** Two rosters over one paragraph need two passages inside it, which means
bounding a clause rather than a block, and the phrases available are mid-sentence fragments of
prose that a rewrite would move for reasons having nothing to do with the lists. The close chose
the wider roster deliberately, since the promise the paragraph makes is that every module is named
and that promise breaks on membership rather than on placement.

**What would close it.** Split the registered passage in two at the sentence that opens the
no-CLI list, with the members of the first being the modules carrying a main guard and the members
of the second being the rest. That is one new reader and two registry entries, and it also decides
whether a name may appear in both halves, since a CLI module is named in the second half whenever
another module is described as its reader. Leave the count alone unless the standing decision
changes, and read
[R-447](447-a-widened-passage-is-caught-only-by-accident.md) first, since two passages inside one
paragraph make a moved boundary easier rather than harder.
