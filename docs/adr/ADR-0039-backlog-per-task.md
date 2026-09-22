# ADR-0039: One file per backlog task, and an index nobody writes by hand

**Status:** Accepted (2026-09-15)

## Context

The two backlogs had grown to 15,021 lines across 24 files: one area doc held 47 entries in 2,279
lines, and the refinements index was 3,956 lines, one table cell a single line of several thousand
words. The two questions people arrive with, **what is left** and **what did this one become**, both
meant reading an area doc end to end and then the index's running ledger for the corrections the
area doc had not picked up.

The backlog documented the failure against itself. A status was written in three places: the entry,
its area doc's `**Open items:**` header, and the area's cell in the index table. The body-overlay
header had gone out of date twice in opposite directions, naming an entry that was finished and
missing one that opened, so the header and its cell agreed at every moment and the agreement was
worth nothing. The memory row read 7 for a day because a close that removed two finished entries
never added the two it opened. The defect is that the layout had three places to write a status
into and nothing comparing them.

## Decision

**1. One task is one file.** `docs/refinements/tasks/NNN-slug.md` and
`docs/host/tasks/NNN-slug.md`. Every top-level entry in the old area docs became one file, and so
did every open item that had been living as a clause inside some finished entry, which is where the
hardest-to-find work had accumulated.

**2. Numbers are stable identities, not an ordering.** A task is cited as `R-042` or `H-007` for
as long as it exists. Numbers are never reused and never renumbered, so a number in a commit
message, an ADR or a conversation keeps resolving. Gaps are normal and mean nothing.

**3. A status is declared exactly once, on the task file's `**Status:**` line**, from a closed
grammar in `scripts/backlog.py`: `open, <state>` over six states; `done`, `declined` or
`satisfied` with a date; and, for host work, `never attempted`, `attempted <date>, inconclusive:
<what happened>`, or `ongoing: <why it never closes>` for an observation over months of use or an
obligation on every change, counted on its own. Nothing else in the repo may restate a status. A
title that states a status verb or a date fails the check, because it would be a second place to
keep correct.

**4. The two states defined by waiting must name what they wait for.** `waiting for its trigger`
and `waiting for a consumer` each require a `**Trigger:**` line; without one a deliberate deferral
cannot be told from a dropped task. The one alternative is the literal `unrecorded`, for tasks that
arrived with nothing recorded about what would reopen them, and the index counts those so the
number can be driven to zero.

**5. An index is two documents in one file.** Above the marker a person writes what the backlog
is and how to work it. Between the markers `backlogindex.py` writes what is in it: the open set
grouped by state, then a roll call of every task by area or session. No number in the generated
half is typed by hand, so no number in it can be wrong about the files it counts.

**6. `just backlog` regenerates; `just check-backlog` fails on any disagreement.** The index
cannot be edited into disagreement with the tasks, because the only supported way to change it is
to change a task file and regenerate. `backlogcheck.py` is one of the cross-tree scans `just check`
runs unconditionally, in CI too.

**7. Every relative link in a markdown file must resolve.** Tasks move and their neighbours get
renamed, and a broken markdown link is the one kind of decay that fails silently. The links are
read from every task file, from each index on its regenerated text, and from every other markdown
file the scan in decision 9 reads, since decision records, readings, runbooks and module docs
link to tasks by file name too.

**8. Closure records stay.** A task that is done or declined keeps its file forever: several
entries correct their own origin ADR, so the record of what a deferral became is often worth more
than the deferral was. The roll call is where they live, and the open set is not read past them.

**9. Every `#fragment` in the repo is checked against the headings its target really has**
(`scripts/backloganchors.py`). A renamed heading strands its readers while the path keeps
resolving, one level past what decision 7 catches. Sources are every markdown file the scan reads,
since most pointers into a backlog index live in decision records, runbooks and module docs. A
target is checked when it is a document this same scan reads (`markdown_files`, over `treewalk`),
so one list decides both what may be read and what may be asserted about, and a vendored or built
tree is invisible in both directions. A markdown target the scan does not read is reported rather
than skipped (missing, outside the tree, or vendored, which the path tells apart); a fragment on a
target that is not markdown, such as `body.proto#L42`, is a line anchor and is not checked. A
backlog index is checked against its rendering: its anchors are read off the hand-written halves
around the block the run has just rendered, the document `just backlog` is about to require on
disk, and an index that cannot be rendered is skipped rather than checked against the stale file. A
`#` inside a fenced block is not a heading. Each problem is reported as `path:line`.

**10. The slug rule states what it claims, and a heading it cannot slug is refused.** The rule is
`DROPPED.sub("", heading.lower()).replace(" ", "-")` over the heading's source line, with repeats
numbered from the second. It is exact whenever every markdown construct in a heading is built from
characters it already drops and removes no text, which plain prose, punctuation, code spans and `*`
emphasis all satisfy. `scripts/headingshapes.py` refuses the six forms that do not: a bracketed
span (any of the four link forms, or a literal pair), angle-bracket markup, closing hashes,
underscore emphasis, an entity reference, and a setext underline. An underscore inside a word is
never reported. A document with a refused heading has its anchors left unknown rather than guessed.
Each refusal names the file, the line, the heading, the reason and the fix: the bracketed span's
fix (`QUOTED`) says to quote the brackets in a code span, which both sides drop, or to write the
heading without them; the other five print `PLAINLY`, plain text under leading hashes. Refusal was
chosen over imitating a renderer, because a wrong transform produces an anchor the check accepts
and no reader can follow, while a too-wide detector is seen at once.

**11. A field wraps like the prose around it.** The grammar reads a field's whole value, joining
its continuation lines with one space, and ends the field block at a blank line, the rule markdown
uses to end a paragraph. Reading only the first line had silently truncated two wrapped triggers in
the index. Inside the block a line starting with `**` is a field or an error, never a continuation,
so a field line missing its colon fails instead of vanishing into the value above it.

**12. An open task records the day its claim was last checked.** A task of either kind may have
`**Verified:** YYYY-MM-DD`, the day somebody last compared its claim with the code. It is a date
because a verification is a reading taken at a moment. The value must parse as an ISO date through
the status line's `_parse_date`; a closed task may not have it, since its record already says what
was found, and neither may an ongoing host item, whose claim is checked again on every change. A
future date is accepted, so no clock is read inside the check. On a host task the date covers the
code half of its claim, which moves while the hardware half stays out of reach and is recorded by
`attempted`.
The index renders the date after the entry's `Reopens when:` sentence (each trigger normalised to
end in one full stop) and counts dated entries in a sentence under `What remains`, not in the
headline, which is a partition an overlapping count would break.

**13. The write run checks the links of the index it writes.** `check_links` in
`scripts/backlogcheck.py` takes each source with the text to check: the task files' own text, and
the spliced index rather than the file on disk. Reading the old index let a run that wrote a broken
link pass and failed the run that removed it. An index whose markers are missing has no spliced
text, so its links are not checked on a run that is already failing. A link inside a `Trigger`
stays allowed: the index renders it at another depth, and the write run that does so reports it on
that same run.

## The work stream

The point of all of the above is that finishing a task is one edit and the index follows. The
whole procedure:

1. **Pick.** Read `## What remains` at the top of the index. It is generated, so it is complete.
   Buckets are ordered by what unblocks them, not by priority.
2. **Check the claim before starting.** A task file records what somebody once measured, never
   what the tree does now. Open the code and check the claim first. This rule is inherited from the
   old backlog, which learned it the hard way: one entry described a mechanism that had been
   deleted thirty two minutes after the entry was written, and it was restated twice and put to the
   user twice before anybody checked.
3. **Work it**, under the usual Definition of Done in [AGENTS.md](../../AGENTS.md).
4. **Close it.** In that one file, change the `**Status:**` line to `done`, `declined` or
   `satisfied` with today's date, and add a `## History` line saying what it became. That section
   is the record of the close. Edit the origin ADR in place only when the close changed the decision
   it states, and put a measurement the decision rests on in its readings record under
   [docs/readings/](../readings/README.md).
5. **File what the close opened.** If finishing it raised new work, add a task file with the next
   free number and name it in the History of both. The old backlog's most valuable habit was
   recording that closing an entry opens others; the count that made it visible is now rendered,
   so the habit is all that is left to keep.
6. **Regenerate** with `just backlog`, and commit the index with the task file.

Forgetting step 6 fails `just check` rather than leaving the index quietly wrong, which is the
difference this ADR buys.

## Consequences

- "What remains" is answered by one generated section instead of 24 docs reconciled against a
  ledger, and a count in the index cannot disagree with the files. Whether a task file's prose is
  still true of the tree is not machine-checkable, which is why step 2 of the work stream is a rule
  for people.
- The tree holds several hundred small files; the cost is paid by the file browser, not by the
  reader, who navigates by the index. Per-area docs are gone, and every inbound link points at the
  index or at a task.
- The bucket headings include their counts, so their anchors change whenever a task opens or
  closes; a pointer aimed at one is checked from the first regeneration.
- Six heading forms cannot be written in this repo's prose. A heading whose brackets are prose has to
  be rewritten; whether the rule should honour an escape or a per-line marker waits on
  [334](../refinements/tasks/334-a-heading-whose-brackets-are-prose.md). A code span delimited by
  two backticks is read as two empty spans and its contents refused
  ([677](../refinements/tasks/677-a-double-backtick-code-span-is-torn-apart.md)).

## Alternatives rejected

- **Keep the area docs and check their headers.** A check over three restatements still leaves
  three places to edit; removing the restatements is better than checking them.
- **One file per area with a generated header.** It fixes the counts and leaves the reading volume.
- **Numbers within an area (`memory-01`).** An area can change, and the identifier would stop
  resolving.
- **YAML frontmatter.** The bolded field lines parse as well and read as prose, like every other doc
  here.
- **Deleting closure records**, for the reason in decision 8.
- **A hand-written index that a check compares against the tasks.** Reporting a difference a
  person applies by hand is a regeneration step with extra work and a chance to apply it wrong.
- **Refusing a wrapped field.** A task file is read rendered, where a wrapped field is one
  paragraph; refusing it would make one line kind the only one not wrapped by hand, hardest on the
  longest triggers.
- **Choosing targets by what git tracks, or everything under the root.** The heading set is read
  off the working tree, and an unstaged document is an ordinary mid-slice state; checking vendored
  trees asserts what someone else's `README.md` renders.
- **Resolving a bracketed span against the document's link reference definitions.** It would be the
  only check needing more than the heading it reads, and a heading that looks like a link and is
  not one misleads a reader before it misleads the check.

## Related

- [repo checks](../modules/repo-checks.md) (the backlog scripts' contract),
  [docs/refinements/index.md](../refinements/index.md), [docs/host/index.md](../host/index.md),
  [docs/readings/](../readings/README.md).
