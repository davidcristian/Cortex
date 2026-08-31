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
account is worth keeping because each is the same defect in a different form:

- A status was written in three places: the entry itself, its area doc's `**Open items:**`
  header, and the area's cell in the index table. Keeping three restatements true by hand is the
  whole job, and it was not done.
- **A count that is right by cancellation shows neither of its errors.** The body-overlay Open-items
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
dropped. The gate rejects the file otherwise.

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

The point of all of the above is that finishing a task is one edit and the index follows. The
whole procedure:

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
change, so an identifier built from the area stops resolving the moment the area changes. Global
numbers cost one lookup and never move.

**YAML frontmatter instead of bolded field lines.** Rejected. The field lines parse exactly as
well and still read as prose to a person opening the file, and every other doc in this repo is
plain prose markdown. A machine-readable header is not worth being the only file shape here that
opens with a fence of metadata.

**Delete the closure records to shrink the backlog.** Rejected outright, on the old layout's own
reasoning, recorded above as decision 8.

**Let the index be hand-written but check it.** Rejected. A check that reports a diff a person
must then apply by hand is a regeneration step with extra work and an opportunity to apply it
wrong. Generating is the same code with the failure mode removed.

## Addendum (2026-08-16): a pointer's anchor is checked too, against what the index renders

Decision 7 above holds a link's **path** to resolving and stops there. This migration also
retargeted every pointer at an area onto an **anchor**, `refinements/index.md#memory`, and nothing
read the fragment. Those anchors were all true, for a reason that was never a guarantee: the roll
call emits one `### <area>` heading per area and no area was empty. Rename an area, or close and
move the last task out of one, and the heading stops being rendered while the link keeps
resolving, so the reader lands at the top of a long index with no idea which part was meant. That
is the same silent rot decision 7 exists to catch, caught one level short.

`backloganchors.py` now closes it, and three choices are worth recording because each could
sensibly have gone the other way.

**The anchor set is read off the spliced index, not off the committed file.** What the gate
compares against is the hand-written halves of the index wrapped around the block it has just
rendered, which is the document `just backlog` is about to require on disk. Reading the committed
file instead would judge fragments against a document nobody intends to keep, so a stale index
would report a hundred dead anchors on top of the one staleness problem that explains them. It
also means the check needs no second list of headings to keep in step with the renderer: whatever
`render` emits is an anchor, including headings it may grow later.

**Both halves of the index offer anchors.** The generated roll call renders one heading per area
or sitting, and the prose above and below it carries headings people cite as well, the host
index's own bring-up section among them. So the set is every heading in that spliced document
rather than only the ones this repo's renderer produced. A `#` inside a fenced block is not a
heading, which matters because the host index carries runbook fences full of shell comments.

**Sources are repo-wide; targets are not.** At the time of writing, 251 pointers in the repo aim
at a heading in one of the two indexes, and only 77 of them are written inside the backlog. The
other 174 live in decision records, runbooks and module docs, which are exactly the readers a
rename strands, so a scan restricted to the backlog's own files would have left the majority
unguarded while reporting green. Reading every markdown file under the root costs a walk of the
tree and a read of its 374 markdown files, which measured 12 ms. The other direction is
deliberately not taken: a fragment aimed at any
document that is not a backlog index goes unjudged, since that needs a heading set per document in
the repo and is a wider scan over a wider input. Counting that wider population is what turned up
the one stale anchor already in the tree, the host index aiming at
`ADR-0030-brain-handoff.md#risks-flagged-for-user-review` against a heading that now reads **Risks
flagged for maintainer review**, renamed by the pass that took every person out of this repo's
prose. It is fixed, and it is the whole argument for the residual: nine fragments aim outside the
two indexes, eight of them are `README.md` linking itself, and the ninth was wrong.

Two smaller consequences. The bucket headings carry their own counts (`### Fix when it bites
(62)`), so their anchors change whenever a task opens or closes; nothing points at one today, and
anything that starts to will be held to it from the first regeneration. And the gate was proved
able to fail before being trusted, on a copy of the real tree, in five ways: an area renamed, an
area emptied by moving its last tasks out, a rename whose pointers live in task files as well as
in a decision record, a renamed host sitting, and a renamed hand-written heading that the index
links to from within itself.

## Addendum (2026-08-17): a field wraps like the prose around it

Decision 3 puts a status on one `**Status:**` line, and the grammar reading it took "one line"
literally for every field: `_read_header` matched each line against the field pattern and stopped
at the first line that did not match. A field whose value ran past the column this repo wraps at
therefore lost everything after its first line, and lost it silently whenever the field that
wrapped was the last one in the block. Two task files were in that state. R-290's trigger rendered
in the index as "a coverage failure where the relayed `rustc` line is not enough to settle whether
the", stopping mid clause and dropping the second of the two conditions it names, which is the one
that would make the check free. R-285's lost the clause saying which of three positions the
shipped grammar leaves unanchored. In both, the index disagreed with the file it was generated
from, and nothing failed.

A wrap anywhere else was already loud: the block ended early, a required field went missing, and
the gate named the file. So the silent case is exactly a wrapped last field, and the field that
wraps in practice is the one carrying a sentence, `Trigger`.

**The grammar now reads a field's whole value, joining its continuation lines with a single space,
and ends the block at a blank line.** The alternative was to refuse a field that wraps, which
would also have made the truncation loud. It was rejected on three counts.

A task file is markdown that people read rendered, and `**Trigger:** ...` followed by an
unindented line is one paragraph in every renderer, so the file already shows the whole sentence
to a person. The defect is that the parser read less than the document says. What closes it is
making the parser agree with the renderer, not shrinking what the document may say.

Every other line of prose here is wrapped by hand near a column, the bodies of these same task
files included. Refusing a wrapped field makes one line of one file kind the sole exception, and
the constraint falls hardest on the longest and most informative triggers; the two found here are
180 and 250 characters. That puts a temptation to rewrap in front of every future author with a gate
failure behind it, which is recurring friction bought in exchange for a parser fix made once.

Nothing else in this grammar is presentational. A field name, a status verb and a date are values,
and where a line happens to break inside a value is not one. Making the source column matter to the
grammar would be the only rule here that reads the shape of a file rather than what it says.

The end of the block is the one question joining has to answer, a continuation line and the first
line of the body being the same text. It ends at a blank line, the rule markdown itself uses to
end a paragraph, and one all 314 task files already obey: a field block glued to a body is
something nobody has written, because it would render as a single paragraph.

**One guard comes with it, so a silent truncation is not traded for a silent absorption.** Inside
the block, a line starting with `**` is a field or an error, never a continuation. Without that
rule `**Trigger** a second adapter arrives`, a field line missing its colon, parses clean and
becomes part of the `Origin` value above it; `Origin` is rendered nowhere, so the mistyped field
would simply vanish. It now fails, quoting the line. The cost is that a value may not wrap onto a
line whose first characters are bold, which fails loudly with a message saying what to do and is
fixed by rewrapping the sentence.

Regenerating afterwards rewrote both entries in `docs/refinements/index.md` to their full text,
which is the whole of the visible effect.

## Addendum (2026-08-17): every fragment is judged, and the rule for which targets may be

The anchor addendum above drew its boundary at the target: a fragment was judged when it aimed at
one of the two backlog indexes and ignored when it aimed at anything else. That was the right
scope for the pass that built the machinery, and it left a residual, because the argument for
checking a fragment at all never mentioned the backlog. A heading renamed in a decision record
strands its readers exactly the way a renamed area does, and the one stale anchor that pass turned
up was of that kind: the host index aiming into `ADR-0030-brain-handoff.md`, broken by the sweep
that took every person out of this repo's prose. The scan now judges a fragment wherever it points,
and this records the rule that makes that safe.

**The population, recounted.** 389 markdown files carry 262 fragments. 253 aim at a backlog index
and were already gated; the other nine are eight `README.md` links to its own sections and the host
index's one pointer into that decision record. None is wrong today. So the widening buys nine
pointers now and an unbounded number later, which is the honest accounting: the value is that the
next sweeping rename cannot pass silently, not that anything is broken this morning.

**A target is judged when it is a document this same scan reads.** `markdown_files` already
decides which markdown is this repo's own prose, skipping the vendored and built trees, and that
decision is now the rule for both halves of a link rather than for sources alone. One list decides
what may be read and what may be asserted about, so a tree this repo does not maintain is invisible
here in both directions and cannot drift into being judged by one rule while excluded by another.

Two alternatives were weighed. **Judging whatever git tracks** is the more precise definition of
"prose this repo ships", and it is the test `bindcheck.py` already applies, but it takes its answer
from the wrong place: the heading set is read off the file in the working tree, so what may be read
should be settled by the working tree too. Gating on the index would also fail a document that has
been written but not yet added, which is an ordinary state in the middle of a slice, and would make
the gate's verdict depend on what happens to be staged. **Judging everything under the root** is
this rule without the exclusion, and the exclusion is the whole point: asserting what a vendored
`README.md` renders is precisely the overreach the residual warned about.

**Fail closed, with one question left unasked.** A markdown target the scan does not read is
reported rather than skipped, because skipping whatever cannot be answered for is how the stale
anchor already in the tree survived every gate. That one message covers three causes, a target that
is missing, one outside the tree, and one inside a vendored or built tree, and the reader can see
which from the path. The single carve-out is a target whose name is not markdown: `body.proto#L42`
is a line anchor, an addressing scheme with no headings to be right or wrong about, so the gate's
question has no meaning there rather than an unknown answer. Reporting those would forbid a
legitimate idiom and catch nothing.

**A backlog index keeps answering out of its rendering.** The first anchor decision recorded above
survives the widening intact, and it now needs saying twice: an index is registered as a target
even on a run that could not work out what it renders, so a broken backlog is skipped rather than
answered for out of the stale file on disk. Without that, a missing marker would be reported once
and then again as a hundred dead anchors read from a document nobody intends to keep.

**What the slug rule was checked against.** The rule is one regex approximating what a renderer
does, so it was measured against the headings this repo actually has: 1,918 of them across those
389 files. Two shapes are present and both drop a character standing between two spaces, an
ampersand in fourteen headings and an arrow in seven, which leaves the pair of hyphens neither the
renderer nor this rule collapses; both are now pinned by a test. Six files repeat a heading, which
the numbering from the second occurrence covers, and the host index's runbook fences are full of
shell comments, which the fence rule covers. Four shapes where this regex and a renderer's slugger
would disagree are absent from the tree: a heading containing a link, one containing an HTML tag,
one closed with trailing hashes, and one using underscores for emphasis. A setext heading, written
as an underline rather than with a leading hash, is invisible to the scan entirely and is likewise
absent. R-292 records all five and names the trigger.

**Proved able to fail before being trusted**, on the real tree in both of the new shapes. Renaming
`## Risks flagged for maintainer review` in `ADR-0030-brain-handoff.md`, which is the exact rot this
whole line of work started from, was reported as `docs/host/index.md:602`. Pointing a `README.md`
fragment at a file that is not there was reported as `README.md:34`. Both were restored and the gate
returned to green over all 262 pointers.

**A pointer now reports the line it is written on**, which the two-document scope did not need and
389 files do. It joins the other scans here, all of which report `path:line`.


## Addendum (2026-08-18): the slug rule states what it claims, and refuses the rest

The repo-wide-anchor addendum pointed the fragment check at every markdown file in the tree, and
the deferral it opened named the cost: the slug rule is
`DROPPED.sub("", heading.lower()).replace(" ", "-")` over a heading's **source** line, while a
renderer slugs its **rendered** text, and those are not the same string. Five shapes where they
disagree were enumerated and measured absent. Re-deriving that measurement before building found
it still true, in a tree that has grown since (404 markdown files, 1,993 ATX headings, 267
fragments, against the 389/1,918/262 recorded then), and found a **sixth**: an entity reference,
whose letters this rule keeps as text where a renderer resolves the whole of it to one character,
so a heading pairing two words with `&amp;` would slug with `amp` in the middle of it. Absent too.

**The closure is refusal, not renderer emulation, which is the opposite of what the entry
proposed.** The entry's own plan was four inline transforms plus reading setext headings, and its
own stated reason for waiting was that a transform written against no example is a guess. That
reason does not expire when the transforms are written: a wrong transform produces a wrong anchor,
and a wrong anchor is a **silent accept**, a pointer the gate passes that no reader can follow.
Refusing costs about the same lines and cannot invent an anchor. Its two failure modes are both
loud or inert: a detector too wide reports a legitimate heading, which someone sees immediately,
and a detector too narrow leaves the old approximation exactly where it already was.

1. **The claim is now written down.** The rule is exact whenever every markdown construct in a
   heading's source is built from characters it already drops and carries no text away with it.
   Plain prose, punctuation, code spans and `*` emphasis all qualify, a backtick and an asterisk
   being dropped on both sides, which is why the 133 code-span headings and 4 starred ones in this
   tree were never at risk. The six shapes that do not qualify are named, and each makes the rule
   read a heading MORE literally than a renderer does.
2. **The refusal lives in `scripts/headingshapes.py`.** Wiring it into `backloganchors.py` took
   that file to 334 lines, so the responsibility split along the seam that was already there:
   what a heading *is* moved out, and what anchors a document offers and which pointers land
   stayed. `backlogcheck.py` needed no change; it already prints whatever the anchor scan returns.
3. **A document carrying one has its anchors left unknown**, exactly as an index too broken to
   render does, rather than being judged on the anchors the rule would have guessed. Telling a
   reader that such a document "does not offer" a heading would be an accusation the rule cannot
   support, and the run is already failing on the heading itself.
4. **An underscore inside a word is never reported.** Six headings here carry one after code spans
   come off (`session_id`, `os_*`, `body_client`, `cortex_core`, `edit_scheduled`), CommonMark
   reads none of them as emphasis, and a detector without its word-boundary guard reports
   `brain/packages/body_client and cortex_core` as a violation on the spot, which a test pins.

**Proved before it was trusted.** A scratch document carrying all six shapes was written into
`docs/` and the gate run against the real tree: six problems, one per shape, each naming the file,
the line, the heading, the reason, and the remedy, and none of them fired on the legal headings
sitting beside them in the same file. The document was then deleted and the gate returned to
`backlogcheck OK`. Five further mutations each make a distinct set of tests fail: dropping the
unknown-anchor rule, unwiring the shape scan from the gate, deleting the entity detector, widening
the emphasis detector, and not reading setext underlines.

**The taste risk, flagged rather than buried.** This converts a silent approximation into a house
style: six heading shapes are now unwritable in this repo's prose, and one of them
(`## <kbd>Ctrl</kbd>+N`) is a heading somebody might genuinely want. The tree carries none of the
six today, so nothing had to be rewritten, and the message tells an author exactly what to write
instead. If one of the six is ever wanted badly enough, the answer is to render that one shape and
prove the transform against the real heading that asked for it, which is a better position to
write a transform from than this one.

## Addendum (2026-08-20): a bracketed span in a heading is refused, target or no target

The addendum above refused six heading shapes and left one form of the first uncaught. Its link
detector looked for a bracketed span **followed** by an opening parenthesis or bracket, which finds
an inline link, an image and both reference forms, and misses the shortcut form: a bracketed label
alone, which markdown resolves against a link reference definition somewhere else in the document.
That residue was filed as
[R-307](../refinements/tasks/307-shortcut-reference-link-in-a-heading.md), and it is closed here by
taking the wider of the two branches that entry named.

**The detector drops its trailing mark**, so the brackets alone are the shape. The alternative was
to collect each document's link reference definitions in one pass and refuse a heading whose label
names one. That is the more precise rule and the worse one. It would be the first thing in this
gate needing more than the heading it is judging, it settles a heading's verdict from a line
hundreds of lines away, and it accepts the shape whose whole problem is that a reader cannot tell
what it is either: a heading that looks like a link and is not one misleads before it misleads this
gate. Refusing the span outright costs one regex and no second pass.

**The price is a literal pair of brackets in a heading**, and it is worth naming rather than
burying, exactly as the six were. A heading that means its brackets literally now has to be written
another way, and the message says so. There is no escape hatch, deliberately: the ban is a house
style with nothing to escape from today, and inventing a per-line exemption for a shape nobody has
written would be machinery aimed at a hypothetical. If one is ever wanted, that is when the exemption
gets designed against the real heading that asked for it
([R-334](../refinements/tasks/334-a-heading-that-means-its-brackets.md)).

**The refusal's own sentence moved with the rule.** It used to say the heading carries a link whose
target this rule would join onto the anchor, which describes only the half that has a target. It now
says the heading brackets a span, which markdown may make a link and this rule always reads
literally, and that is true of every one of the four link forms and of a literal pair besides. The
sentence is a named constant so the suite asserts what the gate prints rather than a paraphrase of
it, and the constant kept its name.

**Measured before changing anything, and proved able to fail after.** A sweep over all 431 markdown
files in the tree on the day of the change found **zero** link reference definitions and **zero**
headings carrying a bracket at all, code spans included, out of 2149 ATX headings, so the stricter
rule rewrote nothing. Three cases were added beside the six already proved: the shortcut form, the
collapsed form, and a bracketed aside nobody meant as a link, each refused by name. The old detector
was run beside the new one over the same six bracketed headings and passes the shortcut form and the
aside, which is the hole this closes. (**Two counts in that sentence pair are corrected here.** It
was written as four cases added and five headings compared. Three cases were added, which is what
the commit message and the entry both say and what the suite carries at
`scripts/tests/test_headingshapes.py`, and the bracketed cases the old detector was run against
number six.) End to end, a heading reading `## 3. Validate delegation against
[the rules]` planted in a real runbook takes `backlogcheck` to exit 1 naming the file, the line, the
heading and the remedy, and the tree returns to `backlogcheck OK` when it is removed.

## Addendum (2026-08-20, later): the remedy the bracket refusal inherited does not fit it

A close-out review of the change above found the sentence it prints ending in a remedy that
describes the heading it is refusing. The six refusals share one remedy, `PLAINLY`, telling the
author to write the heading as plain text under leading hashes. Five of the six are markup, so that
is a real instruction. The sixth, as this addendum widened it, reaches a heading that is already
plain text under leading hashes and carries no markup at all, and tells its author to do what they
did.

The addendum above also claims more for the message than the message says. It reads that a heading
meaning its brackets literally now has to be written another way "and the message says so". The
message names the shape and prints the shared remedy, and neither half names a way out. **That
sentence is corrected here**: what says so is this record, not the gate.

It is filed rather than fixed because the remedy cannot name an answer that has not been chosen.
[R-334](../refinements/tasks/334-a-heading-that-means-its-brackets.md) is the entry holding that
choice, between rewriting the heading, an escape the rule honours, and a per line allow marker, and
a remedy that promises an escape before one exists is worse than one that fits badly. The two move
together, and the smallest honest version of the fix is one remedy per shape, which is the shape the
constants already have. Filed as
[R-344](../refinements/tasks/344-a-remedy-that-repeats-the-heading.md).
