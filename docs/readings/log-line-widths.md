# Readings: log line widths

How long a rendered brain log line can get, against the length at which the container log driver
splits a message. Cited by [ADR-0051](../adr/ADR-0051-log-line-rendering.md), decisions 12, 15 and
16. An absolute width depends on the level, logger, message and key names a run uses and on the
    digits in each cut marker, so it reproduces only within one run's settings; what stays the same
    between runs is the field count, the marker count and how many driver messages one line becomes.

## The driver's cliff

**2026-08-20.** A container's log driver ends a message at 16 KiB, so a rendered line of 16,383
characters plus its newline is the longest that stays one entry. `docker compose logs` joins the
pieces back into one line; `docker compose logs -t` stamps every piece, and the stamps appear inside
the line (a split message read back as one line of 16,446 bytes with two timestamps); `--tail`
counts pieces, so over a log whose last record was a 100 KB line, `--tail 3` returned one 34,517
character fragment of a value and nothing naming it. Bounded at `VALUE_CHARS`, the same two records
rendered at 2,161 and 2,119 characters, one entry each. Method: records of known width through the
real `configure_logging` in the shipped brain image under the base compose stack, read back three
ways.

## Fields at the bound

**2026-09-12.** Through the shipped `PlainFormatter`, one line with every field cut at the bound:
seven fields render at 14,526 characters and fit under the cliff; eight render at 16,598 and do not.
Method: a synthetic record rendered in the working tree through `brain/.venv`.

## The widest line each shipped sink builds

**2026-09-15.** Every field whose text the brain does not choose set past `VALUE_CHARS`:

| sink | wide fields | widest line | of the 16,383 cliff |
| --- | --- | --- | --- |
| tool audit, plain | 5 | 10,593 | 65% |
| recall trail, plain | 1 plus a wide `session_id` | 4,464 | 27% |

On 2026-09-12, four million-character audit fields rendered at 8,437 characters `plain` and
4,000,296 `packed`, which is 245 driver messages against one. One trail record at its shipped caps
(twenty dropped, five hits, uuid4 ids) renders at 2,258 characters `plain` and 2,478 `packed`.
Method: `brain/packages/orchestrator/tests/test_widest_line.py`, which asserts the line against the
cliff rather than any width.

## The recall trail on a live stack

**2026-08-26 and 2026-08-27.** 466 trail lines over two blocks with the shipped `judge` rank and
`CORTEX_MEMORY_RECALL_AUDIT=1`, 41 notes a session, 75 distinct queries, on the 24 GB card:

| candidates dropped | kept | lines | `dropped` field | whole line |
| --- | --- | --- | --- | --- |
| 17 | 3 | 9 | 1,246 to 1,249 | 1,784 to 1,800 |
| 18 | 2 | 43 | 1,313 to 1,324 | 1,724 to 1,749 |
| 19 | 1 | 342 | 1,389 to 1,399 | 1,701 to 1,724 |
| 20 | 0 | 72 | 1,465 to 1,473 | 1,691 to 1,699 |

No value was cut. Twenty dropped is a `demur`, the judge keeping nothing. The widest field is on
the narrowest line: a kept hit costs about 100 characters against a dropped candidate's 73, so the
line's maximum comes from the rarest cohort. The widest line is 11% of the cliff. A synthesized
field of uuid4 ids and random scores measured 1,458 to 1,476, bracketing the live range. Method:
`just recall-width`, running `orchestrator/tests/recall_trail_probe.py` inside the brain container,
then `scripts/trailwidth.py` over the captures (kept under the gitignored `measurements/`).
