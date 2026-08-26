# The repo map names every gate module in a block no reader here can see

**Status:** open, fix when it bites
**Trigger:** a module is added to `scripts/` and the repo map keeps describing the tree that
existed before it, which is the same drift the module contract's own listing was just held
against, one document over.
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-26 by the close of
[R-413](413-the-module-contracts-part-list-is-held-by-nobody.md), which registered the Public
contract paragraph of [modules/repo-gates.md](../../modules/repo-gates.md) as a roster over every
module in `scripts/` and left a third copy of that same set alone.

The `scripts/` entry of the repo map in [AGENTS.md](../../../AGENTS.md) names all forty eight
modules in the tree, each with what it holds, and it names the ten registry parts among them with
a tally in front of them. Measured on the day this was filed, it is complete and correct. It is
also held by nothing, and four of its names were added by the same hand that added the four
modules under it.

**Why it was left.** The reader that holds the other copies takes a name from a **code span**, and
the repo map has none: it is a fenced block of plain text laid out in columns, where every module
name is a bare word. Teaching the name reader to take bare words needs a third spelling shape, and
that shape is only safe inside a bounded passage, since a bare `linecap.py` in ordinary prose
would otherwise read as a roster entry wherever it appeared. That is a real design decision rather
than a line of code, and it was not the decision either closing entry was about.

**What would close it.** A third way of writing a roster down, bare names matching a pattern
inside a passage, plus one registry entry bounding the repo map's `scripts/` entry against the
lines above and below it. Check what that costs the other trees first: the same repo map names
every Rust crate and every brain package in the same shape, so the shape that lands here decides
whether those become rosters too or stay prose. The tally in front of the parts stays a hand count
either way, under the standing decision that a document's numbers are its own business.
