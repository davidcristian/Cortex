# Decision records

An ADR here states one architectural decision as it currently stands: what was decided, why, and
what follows from it. A reader opens it to learn the rule that applies today, so it is short enough
to read in one go and contains nothing that is no longer true.

## The rules

- **One decision per record, at most 250 lines.** A record that needs more is two decisions, or it
  contains measurements or history that belong elsewhere. `scripts/linecap.py` fails `just check`
  on any markdown file over the limit, this README included
  ([ADR-0011](ADR-0011-body-v1.md) decision 12).
- **Edited in place.** When the decision changes, the record is rewritten to state the new decision
  and its `**Status:**` date moves. Git keeps every earlier version, so nothing is appended: a
  record never ends with a dated list of later changes.
- **Measurements live in [docs/readings/](../readings/README.md).** A record states the figure a
  decision turns on and links to the readings record with that measurement, its date and its
  method. A mutation table is neither: AGENTS.md requires it in the body of the commit that makes
  it.
- **Closing a backlog entry is recorded in its task file's `## History`**
  ([ADR-0039](ADR-0039-backlog-per-task.md)). It changes a record only when it changed the decision
  that record states.
- **Number and filename are permanent.** `ADR-NNNN-slug.md`, never renumbered, so every citation
  keeps working. A decision replaced by another keeps its file, and its status says which record
  replaced it.
- **Headings are stable.** Other documents link to a section by its anchor, so a heading is renamed
  only together with every link to it.

The prose rules in [AGENTS.md](../../AGENTS.md) apply in full, including writing a measurement of
this machine as a ratio of its own numbers.

## The format

```
# ADR-NNNN: <title>

**Status:** Accepted (<date the decision last changed>)   or   Superseded by ADR-MMMM

## Context
Why a decision was needed, in a few short paragraphs.

## Decision
The numbered decisions, each with its reason in a sentence or two. Subsections with stable
headings are fine.

## Consequences
What follows: invariants, costs, what the decision rules out.

## Alternatives rejected
Only the ones a future reader would otherwise propose again, one or two lines each.

## Related
Module docs, runbooks, readings records and other ADRs.
```

The catalogue of every record, with a line on what each one decides, is in
[docs/index.md](../index.md#decisions-adrs).
