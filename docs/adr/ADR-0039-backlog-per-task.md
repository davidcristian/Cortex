# ADR-0039: One file per backlog task, and an index nobody writes by hand

Date: 2026-08-11. Status: accepted.

## Context

The two backlogs had grown to 15,021 lines across 24 files. One area doc was 2,279 lines and
held 47 entries; the refinements index was 3,956 lines, and the table cell describing a single
area was one unbroken line of several thousand words. Recording a deferral was still cheap, but
the two questions people actually arrive with, **what is left** and **what did this one become**,
had both become expensive: answering either meant reading an area doc end to end and then
reading the index's running ledger for the corrections the area doc had not picked up.

The failure mode is not a guess. This backlog documented it against itself, three times, and each
account is worth keeping because each is the same defect wearing different clothes:

- A status was written in three places: the entry itself, its area doc's `**Open items:**`
  header, and the area's cell in the index table. Keeping three restatements true by hand is the
  whole job, and it was not done.
- **A count that is right by cancellation hides both of its errors.** The body-overlay Open-items
  line had drifted twice in opposite directions: it still named an entry that had landed and had
  never picked up one that opened. Eleven names either way, so the header and its cell agreed at
  every moment, and the agreement was worth nothing. A reader following it would have opened a
  closed entry and never seen an open one.
- The memory row read 7 for a day because a close that struck two landed entries never added the
  two it opened. There the count did move, and it moved the wrong way.

The lesson the backlog drew from this was to read the entries rather than trust the arithmetic,
which is correct advice and does not scale: it asks every reader to re-derive, from thousands of
lines, a fact the writer already knew. The defect is not that people miscount. It is that the
layout has three places to write a status into and no machine holding them together.

## Decision

**1. One task is one file.** `docs/refinements/tasks/NNN-slug.md` and
`docs/host/tasks/NNN-slug.md`. Every top-level entry in the old area docs became one file, and so
did every open item that had been living as a clause inside some landed entry, which is where the
hardest-to-find work had accumulated.

**2. Numbers are stable identities, not an ordering.** A task is cited as `R-042` or `H-007` for
as long as it exists. Numbers are never reused and never renumbered, so a number in a commit
message, an ADR addendum or a conversation keeps resolving. Gaps are normal and mean nothing.

**3. A status is declared exactly once, on the task file's `**Status:**` line**, from a closed
grammar: `open, <state>` over six states; `landed`, `declined` or `satisfied` with a date; and,
for host work, `never attempted`, `attempted <date>, inconclusive: <what happened>`, or `done`
with a date. Nothing else in the repo may restate it. A title carrying a status verb or a date is
a gate failure, because a title that says `landed 2026-08-06` is a fourth place to keep true.

**4. The two states that are defined by waiting must name what they wait for.** `fix when it
bites` and `dead until a consumer` each require a `**Trigger:**` line. Both states mean somebody
decided not to act, and without a written trigger that is indistinguishable from a task quietly
dropped. The gate refuses the file otherwise.

**5. An index is two documents in one file.** Above the marker a person writes what the backlog
is and how to work it. Between the markers `backlogindex.py` writes what is in it: the open set
grouped by state, then a roll call of every task by area or sitting. No number in the generated
half is typed by hand, so no number in it can be wrong about the files it counts.

**6. `just backlog` regenerates; `just check-backlog` fails on any disagreement.** This is
`cargo fmt --check` pointed at a backlog. The index cannot be edited into disagreement with the
tasks, because the only supported way to change it is to change a task file and regenerate. It
joins the line cap, the dash scan, the constant scan and the bind scan as the fifth cross-tree
scan, run unconditionally, in CI too.

**7. The gate also holds every relative link in a task file to resolving.** Tasks get moved and
their neighbours get renamed, and a broken markdown link is the one kind of rot that fails
silently. It was worth having on the day of the migration alone, when several hundred links
changed depth at once.

**8. Closure records stay.** A landed or declined task keeps its file forever. That rule is
inherited unchanged from the layout this replaces, for the reason that layout gave: several
entries correct their own origin ADR, so the record of what a deferral became is often worth more
than the deferral was. The roll call is where they live, and the open set no longer has to be
read past them.

## The work stream

The point of all of the above is that finishing a task is one edit and the index follows. In
full, and this is the whole procedure:

1. **Pick.** Read `## What remains` at the top of the index. It is generated, so it is complete.
   Buckets are ordered by what unblocks them, not by priority.
2. **Re-derive before starting.** A task file is a record of what somebody once measured, never a
   reading of what the tree does now. Open the code and check the claim first. This rule is
   inherited from the old backlog, which learned it the hard way: one entry described a mechanism
   that had been deleted thirty two minutes after the entry was written, and it was restated
   twice and put to the user twice before anybody checked.
3. **Work it**, under the usual Definition of Done in [AGENTS.md](../../AGENTS.md).
4. **Close it.** In that one file, change the `**Status:**` line to `landed`, `declined` or
   `satisfied` with today's date, and add a `## Trail` line saying what it became. Write the
   dated addendum at the origin ADR, as before.
5. **File what the close opened.** If finishing it raised new work, add a task file with the next
   free number and name it in the Trail of both. The old backlog's most valuable habit was
   recording that closing an entry opens others; the count that made it visible is now rendered,
   so the habit is all that is left to keep.
6. **Regenerate** with `just backlog`, and commit the index with the task file.

Forgetting step 6 is a failed gate, not a silent drift, which is the difference this ADR buys.

## Consequences

- The question "what remains" is answered by one generated section instead of by reading 24 docs
  and reconciling them against a ledger.
- A count in the index cannot disagree with the files, so the three drift incidents quoted above
  are no longer reachable. What a machine cannot check is whether a task file's *prose* is still
  true of the tree, which is why step 2 above stays a rule for people.
- The tree gains several hundred small files. That is the cost, and it is paid to the file
  browser rather than to the reader, who navigates by the index.
- Per-area docs are gone. Every inbound link to one now points at the index or at a task.

## Alternatives considered

**Keep the area docs and gate their headers.** Rejected. The drift is caused by restatement, and
a gate over three restatements still leaves three places to edit and three chances to disagree.
Removing the restatements is strictly better than checking them.

**One file per area with a generated header.** Rejected. It fixes the counts and leaves the
reading volume, which is the complaint that started this. A 2,279-line file with an accurate
header is still a 2,279-line file.

**Number within an area (`memory-01`).** Rejected. A task's area is a fact about it that can
change, and an identity that changes when the fact does is not an identity. Global numbers cost
one lookup and never move.

**YAML frontmatter instead of bolded field lines.** Rejected. The field lines parse exactly as
well and still read as prose to a person opening the file, and every other doc in this repo is
plain prose markdown. A machine-readable header is not worth being the only file shape here that
opens with a fence of metadata.

**Delete the closure records to shrink the backlog.** Rejected outright, on the old layout's own
reasoning, recorded above as decision 8.

**Let the index be hand-written but check it.** Rejected. A check that reports a diff a person
must then apply by hand is a regeneration step with extra work and an opportunity to apply it
wrong. Generating is the same code with the failure mode removed.
