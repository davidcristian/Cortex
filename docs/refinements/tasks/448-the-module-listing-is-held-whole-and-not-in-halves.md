# The check tree's module listing is compared whole, so neither of its halves is

**Status:** done 2026-08-26
**Area:** repo-checks
**Origin:** [ADR-0044](../../adr/ADR-0044-document-rosters.md)

The Public contract paragraph of [modules/repo-checks.md](../../modules/repo-checks.md) makes three
claims and one is checked. It names every module in `scripts/`, which is checked. It sorts them
into the ones with a command line of their own and the ones without, which is not: the registered
list is the whole paragraph, so a module named in the wrong clause passes, and a module that gains
a command line and stays in the second list reads as a library to anyone who trusts the sentence.
And it opens the second list with a count in words, which is a hand count under the decision that a
document's tallies are its own business.

The command-line half is machine-readable in a way the count is not: a module here has one exactly
when it has an `if __name__ == "__main__":` guard, which is one search over the same directory the
list already reads. Splitting the registered passage in two at the sentence that opens the no-CLI
list is one new reader and two registry entries, and it also decides whether a name may appear in
both halves, since a command-line module is named in the second half whenever another module is
described as its reader.

## History

- 2026-08-26: opened by the close of
  [R-413](413-the-module-contracts-part-list-is-held-by-nobody.md), which chose the wider list
  deliberately, since the promise the paragraph makes is that every module is named, and recorded
  the half it was giving up.
- 2026-08-26: closed as the module listing rule of
  [ADR-0044](../../adr/ADR-0044-document-rosters.md), which registered the paragraph as two lists
  bounded on one shared phrase, the members of the first being the modules with a top-level main
  guard and the members of the second the rest. Checking again left the premise intact. Both
  halves were correct on the day this was picked up, fourteen command lines named in the opening
  clause and all thirty four of the rest named after it. The question the entry said the split
  would force, whether a name may stand in both halves, is answered yes in one direction only: the
  second half names seven command-line modules while saying whose reader each library is, so a list
  may declare the sibling set whose names it is allowed to contain, and nothing else is let
  through. That allowance deliberately does not distinguish a name a sentence refers to from one it
  claims, which is filed as
  [R-451](451-a-borrowed-name-cannot-be-told-from-a-claimed-one.md). The count in front of the
  second list stays a hand count, as this entry asked. The same commit closed
  [R-449](449-the-repo-map-names-every-check-module-in-an-unseen-block.md), the third copy of the same set.
