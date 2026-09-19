# Readings

A readings record holds the current measurements that one or more decisions rest on: the figures
an ADR in [docs/adr/](../adr/README.md) or a runbook turns on, kept out of the decision text so
the decision stays short and the numbers stay current.

## The rules

- **One file per subject**, `docs/readings/<subject>.md`, at most 250 lines. A subject is what was
  measured (a model tier's memory, a capture's latency), not the decision that cites it, so several
  decisions may link one record.
- **Current readings only.** A reading that is superseded is replaced, not appended to. Git keeps
  the earlier one.
- **Every reading has three parts**: the date it was taken; the figure in a form a reader on other
  hardware can use, meaning a ratio of the measuring machine's own numbers where the figure
  describes only that machine (the rule in [AGENTS.md](../../AGENTS.md)); and its method in a line,
  naming the recipe, test or command that re-takes it.
- **A reading is not a decision.** What the figure means for the design is stated in the ADR that
  cites it; the record says what was measured, when and how.
- **A mutation table is not a reading.** It is written in the body of the commit that makes it,
  which is where the replay pass reads it from (see AGENTS.md on proving a check can fail).

`scripts/linecap.py` fails `just check` on any markdown file over 250 lines, this README included
([ADR-0011](../adr/ADR-0011-body-v1.md) decision 12). Nothing else checks these files beyond the
repo-wide scans, so a record stays correct only while whoever takes a new reading replaces the old
one in the same change.
