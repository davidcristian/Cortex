# The module contract names the registry's parts twice, and nothing holds either list

**Status:** open, fix when it bites
**Trigger:** a part is added or renamed and the `scripts/` module contract keeps describing the
set that existed before it, which is the first time either list being unheld costs a reader
anything.
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-24 by the close of
[R-408](408-the-registry-shape-counts-places-not-parts.md), which held `registry.py`'s own list of
parts to the files on disk and left the two copies in the module contract as they were.

[modules/repo-gates.md](../../modules/repo-gates.md) names the nine `*couplings.py` files twice:
once in the no-CLI-module listing near the top and once in the `crosscheck.py` bullet, the second
of which also gives each part's subject in a parallel prose list. Both are hand-maintained. A
tenth part lands, `registry.py`'s docstring reddens until it names it, and this document quietly
keeps describing nine. The two copies are already in different orders, the top listing not being
in read order, which is fine and is also the evidence that nobody is comparing them to anything.

**Why it was left.** The close held a module's own docstring to its own directory, which is a
tight loop. Reaching into a document in `docs/` is a different rule and it has a standing decision
in front of it: the registry-shape close declined to gate this document against the registry,
because a document describing the gate is not a far side of the gate and a tally in it goes stale
on the next row.

**What would close it.** Decide whether that standing decision covers a list of **names** or only
a list of **numbers**. The argument that it does not is that a name list goes stale exactly when a
part is added, which is when it should redden, where a tally goes stale on any edit anywhere. The
argument that it does is that this document restates what `registry.py` already declares and now
has held, so its copy is a convenience and a stale convenience is a documentation lag rather than
a lost answer. If the answer is to hold it, the cheapest shape is the one the close already used,
reading the backticked module names out of the document and requiring them to be the files on
disk, and the question is whether both copies are held or only the one that also states each
part's subject.
