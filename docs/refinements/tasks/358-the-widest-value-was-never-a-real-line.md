# The widest value the tree attaches is a synthesis, and no real recall line was ever measured

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-21 by the close of [R-349](349-a-mutation-table-nobody-replayed.md), which
re-measured the figure and found the measurement sound and its provenance misdescribed.

`VALUE_CHARS` is justified by clearing the widest value the tree attaches today, and that value is
the recall trail's `dropped` list at the shipped pool of twenty: 1,458 to 1,475 characters over 200
draws when it was recorded, and 1,458 to 1,476 over a fresh 200 through the shipped
`render_value`, which is the reading the comment carries now. The floor to the character and the
ceiling within one is what two samples of a maximum do, so the number is not in doubt.

**What it is a number about is.** The draw is `uuid4` ids and cosine scores synthesised in process.
No store is involved, which is why it costs two minutes and why the entry that doubted it was wrong
to file it beside the container measurements. A real `dropped` list carries the ids the memory store
actually minted and the cosines pgvector actually returned, and the rendered width is a function of
both: an id spelled some other way, or a score whose float repr is longer than a uniform draw's
typically is, moves the number. Nothing has ever read the width off a line a live stack produced.

**What would close it, and what it costs.** Bring up the memory override (`Postgres` with pgvector
plus the CPU embedder), seed a corpus wide enough that a pool of twenty is a real pool rather than
the whole store, run recalls with the audit sink attached, and measure the rendered `dropped` field
off the lines the container wrote. That is a live run and therefore `integration` marked and out of
the coverage gate. Honest estimate, from the shape of the existing live memory runs rather than
from having done this one: thirty to forty five minutes including bring-up and seeding, with the
seeding the part most likely to run long. The result is worth having whichever way it lands, since
a synthesis that matches the real distribution is a stronger justification than one nobody checked,
and a synthesis that does not is a bound argued against the wrong number.
