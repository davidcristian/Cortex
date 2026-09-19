# The widest value the tree attaches was computed, never read off a real line

**Status:** done 2026-08-26
**Area:** memory
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

`VALUE_CHARS` is justified by clearing the widest value the tree attaches today, and that value is
the recall trail's `dropped` list at the shipped pool of twenty: 1,458 to 1,475 characters over 200
draws when it was recorded, and 1,458 to 1,476 over a fresh 200 through the shipped `render_value`.
The floor to the character and the ceiling within one is what two samples of a maximum do, so the
number is not in doubt.

What it is a number about is. The draw is `uuid4` ids and cosine scores generated in process. No
store is involved, which is why it costs two minutes. A real `dropped` list has the ids the memory
store actually created and the cosines pgvector actually returned, and the rendered width depends
on both: an id written some other way, or a score whose float repr is longer than a uniform draw's
usually is, moves the number.

Closing it means bringing up the memory override (Postgres with pgvector plus the CPU embedder),
seeding a corpus wide enough that a pool of twenty is a real pool, running recalls with the audit
sink attached, and measuring the rendered `dropped` field off the lines the container wrote. That
is a live run and therefore `integration` marked. Estimated at thirty to forty five minutes
including bring-up and seeding.

## History

- 2026-08-21: Opened by the close of [R-349](349-a-mutation-table-nobody-replayed.md), which
  re-measured the figure, found it sound, and found its origin misdescribed: a computation over
  drawn ids and scores, filed beside the container measurements it is not one of.
- 2026-08-26: Done, as [ADR-0051 decision 16](../../adr/ADR-0051-log-line-rendering.md), a probe
  that runs inside the brain container
  (`brain/packages/orchestrator/tests/recall_trail_probe.py`), the `recall-width` recipe that owns
  its docker, and `scripts/trailwidth.py`, which reads the captures back. Two runs on the 24 GB
  card under the shipped `judge` rank, 75 distinct queries against a seeded 41 note corpus, 466
  trail lines, none of them cut. The computed figure held: a whole dropped pool of twenty renders
  at 1,465 to 1,473 characters against the computed 1,458 to 1,476, the real floor higher and the
  real ceiling inside it. The stronger result needed no sample: with the shipped id factory the
  field is 1,101 characters of syntax and id plus twenty float reprs, and no Python float renders
  in more than 24, so it cannot pass 1,581 and `VALUE_CHARS` clears it by 467 whatever the cosines
  do. The comment on `VALUE_CHARS` moves to the measured reading; this file and the commit it came
  from keep the computed one, being statements about a date. Opened by this close:
  [R-453](453-the-harness-reads-one-field-off-a-line-it-has-whole.md),
  [R-454](454-the-readers-needles-are-not-tied-to-the-sink.md) and
  [R-455](455-the-fields-ceiling-assumes-the-shipped-id-factory.md).
