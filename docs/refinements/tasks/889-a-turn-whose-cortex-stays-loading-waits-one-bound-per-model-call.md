# A turn whose cortex stays loading waits one full bound per model call

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Verified:** 2026-10-16

ADR-0054 decision 10 says a turn waits for a cortex that is still loading up to
`CORTEX_INFERENCE_LOAD_WAIT_S` and then ends. `LoadWaitBackend` starts its deadline at each
`stream` call, and `StreamEngines` routes the recall judge, the history recap and the reply through
the same waiting backend (`engines.py`, `_capabilities`). The judge and the recap fall back on an
`InferenceError`, so with a cortex that never finishes loading a turn with recall hits and a folded
history waits three bounds, 360 s at the default, with the loading status shown the whole time.
A scheduled turn's fire is cut at the 300 s lease first.

Reproduction: drive one `LoadWaitBackend` over a backend that always raises `ModelLoadingError`,
with a clock the sleeper advances, through three calls in a row, catching `InferenceError` as the
judge and the recap do. The calls give up 120 s, 240 s and 360 s into the turn.

## What to do

1. Share one deadline among the calls of one turn: a call that reaches the bound ends the wait for
   every later call of that turn, which then fails at once on a loading answer. The backend is
   built per stream, so either build the waiting backend per turn or give it a turn scope the
   engine opens; a deadline shared per stream would make a later turn fail at once.
2. Test with fakes: a turn with a judge, a recap and a reply over a server that stays loading ends
   one bound after its first loading answer; a turn whose server loads inside the bound still
   answers; the next turn waits a fresh bound.
3. State the turn scope in ADR-0054 decision 10 and the runbook's setting row.

## History

- 2026-10-16: filed by the closing audit of the load wait.
