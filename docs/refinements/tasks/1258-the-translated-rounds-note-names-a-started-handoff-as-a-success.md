# The translated rounds note names a started handoff as a success

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)
**Verified:** 2026-11-18

`runs_line` in [tool_replay.py](../../../brain/packages/core/src/cortex_core/tool_replay.py) writes
a successful `escalate_to_brain` run as `handoff started, answer not recorded here`. `runs_said` in
[rounds_languages.py](../../../brain/packages/core/src/cortex_core/rounds_languages.py), which
writes the same list for the French, German, Spanish and Romanian forms of `ROUNDS_SPENT_NOTE`,
still writes that run with the word for a run that succeeded.

Whether a turn that ran out of rounds can list an `escalate_to_brain` run is not checked: the call
ends the cortex's phase, so the note may never name one. Check that first, with a test over
`rounds_note` and a `RunLog` holding that run.

What would close it: either that test showing the run cannot be listed, or a fifth entry in each
`_RUNS` tuple for a started handoff, with its sentences written for review.

## History

- 2026-11-18: filed when `runs_line` stopped writing a started handoff as a success.
