# A coupling copied into a second part and relabelled is two entries checking one thing

**Status:** open, fix when it bites
**Trigger:** a fault is reported twice under two labels for one drift, or `shape.entries` is quoted
in a mutation table and a reader cannot reconcile it with the couplings the registry actually
holds, which is the first time the duplicate costs anybody anything.
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-24 by the close of
[R-412](412-nothing-holds-the-registry-to-its-parts.md), which held the registry's entry count by
requiring every label in `CONSTANTS` to be distinct.

That catches the copy this repo's own design invites: the scan never asks which file an entry came
from, so a coupling moves between parts freely, and a move done as a copy without a delete leaves the
same entry in two parts under the same label. It does not catch the copy that was also renamed. Two
entries carrying different labels over an identical tuple of sites and mentions pass the equality,
pass the label check, and are counted twice by `shape.entries`, which is the same false count of
the collection's size that the label rule was added to catch. A drift at those places is then
reported twice, once per label, and a reader has no way to tell one coupling described twice from
two couplings that genuinely overlap.

**Why it was left.** The close was about holding the parts to the tuple, and the count it added is
over the thing every mutation table already quotes. Measured on the day it landed, no two entries in
the registry share a places tuple, so this is a hole of exactly the kind the one just closed was:
worth naming, not worth a rule nobody has needed.

**What would close it.** Decide whether two entries may ever legitimately name the same places. The
argument that they may is `Relation`: one pair of sites could plausibly be tied as an equality and
as an ordering against a third, and those are two couplings rather than one. If that is real, the
rule is over the places **and** the relation rather than over the places alone, and a fault has to
say which of the two entries is the copy. If it is not, the check is one line beside the label one,
comparing `(sites, mentions, relation)` across `CONSTANTS`. Either way the message has to name both
labels, since the whole failure is that one thing is written down under two names.
