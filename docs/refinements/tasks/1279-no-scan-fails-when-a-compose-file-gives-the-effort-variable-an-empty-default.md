# No scan fails when a compose file gives the effort variable an empty default

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Verified:** 2026-11-21

`CORTEX_REASONING_EFFORT_BRAIN` reaches the brain as a bare key in `docker/docker-compose.gpu.yml`.
An unset variable then never enters the container, and the settings class applies its default,
`medium`; an empty value names no level (ADR-0049 decision 20). Written as
`"${CORTEX_REASONING_EFFORT_BRAIN:-}"`, the form three model file variables of the same compose
file have, an unset variable arrives as an empty string. Every deep reply then names no level, and
the brain logs no line about it.

What is checked, on 2026-11-21 against the tree, the file restored afterwards: with the line
removed, `settingscheck.py` fails and names the setting. With the line rewritten to the empty
default, `settingscheck.py`, `defaultcheck.py`, `crosscheck.py`, `flagcheck.py` and
`rostercheck.py` all pass. A comment above the line is all that says which form it needs. The
live handoff with the variable absent logged `reasoning effort sent`
([readings](../../readings/model-swap.md#a-handoff-on-the-deep-pick)); no test starts a container.

## Proposal

`settingscheck.py` fails when a compose file writes an empty substitution default for a setting
whose settings class reads an empty value as something other than its default. The effort setting
is one such field (`_an_empty_effort_names_no_level` in `config_swap.py`). Read the other settings
classes first: if it is the only one, a list of one name in the scan is enough, and if a second
field gives an empty value a meaning, the scan reads it from the class. Rewrite the line and watch
the scan fail before trusting it.

**What closes it.** The scan failing on the rewritten line, with that mutation in the commit, or a
decline recorded here.

## History

- 2026-11-21: filed from a review of the default's compose line: the removed line fails
  `settingscheck.py`, and the empty default fails nothing.
