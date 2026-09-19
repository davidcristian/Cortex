# Readings: generation bounds

How long a first token takes, how long a delegated reply runs, and which bound a delegated run meets
first. Cited by [ADR-0005](../adr/ADR-0005-llamacpp-engine.md) decision 7 (the stall timeouts) and
[ADR-0048](../adr/ADR-0048-generation-bounds.md) decisions 10 to 12 (the cap and the deadline). What
a full batch holds is in [delegated run holds](delegated-run-holds.md).

## Time to first token on the resident tier

**2026-08-08.** The cortex pick (gemma-4-12B QAT q4_0, 16K context) reached its first token in 4.6 s
alone and in 10.3, 12.0 and 17.5 s across three overlapping `Converse` streams, those three
including the brain-side lease wait spent before the request reaches the wire. The deep pick loads
in 1.9 to 2.6 times the cortex pick's load time on the same card, and its own first token was not
measured. A screen capture adds about 0.6 s for 744 more context tokens. 17.5 s scaled by the worst
load ratio is 45.5 s, and the shipped 120 s is 2.6 times that. Method: overlapping `Converse`
streams against the model host's cortex tier, first-token times taken at the gRPC boundary; load
times from the lineup table in [ADR-0004](../adr/ADR-0004-model-lineup.md).

The stall timeout is a per-read gap and not a total: a loopback server sending one chunk every 0.2 s
under a 0.5 s timeout delivered all 15 chunks over 3.34 s and raised only once it stopped sending
(2026-08-09, the real-socket test in `orchestrator/tests`).

## A delegated reply on the unconstrained shape

**2026-08-11.** The default subagent entry (gemma-4-E4B QAT q4_0) on CPU at the compose file's
shape (`-ngl 0`, `--ctx-size 8192`, `--parallel 2`, thinking off), one subtask per shape:

| subtask | prompt tokens | decoded tokens | wall clock |
| --- | --- | --- | --- |
| one fact | 19 | 2 | 11.5 s |
| one word | 18 | 4 | 20.7 s |
| extract every number from a report | 220 | 125 | 410.5 s |
| summarize that report, keeping every detail | 224 | 199 | 623.8 s |
| open-ended essay on the same report | 224 | did not finish | cut at 577 tokens, 1958 s |

The four narrow shapes span two orders of magnitude of wall clock; the open-ended one has no natural
end on this tier. A whole summarization later measured 222.8 to 324.3 s on the same machine idle
(the batch in [delegated run holds](delegated-run-holds.md)), so the whole-subtask figure is an
interval and 623.8 s is its slow end. Method: direct requests through the shipped adapter.

## A delegated reply on the shape that ships

**2026-09-11.** The same pick with the subagent compose file's flags (`--jinja`, the reasoning-off
pair, `--ctx-size 8192`, `--parallel 2`, so 4096 tokens a slot) at `-ngl 99`
([ADR-0050](../adr/ADR-0050-live-probe-records.md) decision 9), 40 runs of the constrained variant
over four report bodies, with `REPLY_INSTRUCTION` appended by the runner, on build
`b10680-d7bd3bfca`:

| population | runs | decoded tokens | reply characters | reasoning characters |
| --- | --- | --- | --- | --- |
| finished, tokens in `reply` alone | 38 | 250 to 373, median 278 | 906 to 1340 | 0 |
| finished, a trace and then a reply | 1 | 904 | 1003 | 2320 |
| cut at the cap, a trace alone | 1 | 1024 | 0 | 3079 |

The longest answer is 36% of the 1024 cap. Everything past that band was a trace: a run counting
912 decoded tokens on 2026-08-28 was a trace and an answer together. Across the 288 runs of
2026-08-28 on three picks, no run reported as an answer passed 721 decoded tokens, and every run
that reached the cap was a trace or a repetition. Method: `test_envelope_cost_live.py` with
`CORTEX_ENVELOPE_ARMS=constrained` and `CORTEX_ENVELOPE_DRAWS=10`, judged by `envelopejudges.py`.

## Which bound a delegated run meets first

**2026-08-28, rates of 2026-08-25.** In decoded tokens, on a tool-less run over a 261 to 282 token
prompt, with the idle and saturated decode rates of the unpinned CPU tier (1.35 and 0.18 tok/s):

| bound | decoded tokens it admits |
| --- | --- |
| the cap | 1024, per completion |
| the run deadline, 2400 s | about 3222 idle, about 425 saturated |
| the slot's context, 4096 | about 3820 |

On an idle host the cap binds first; the deadline binds before the context at both ends. With tools
the cap applies per completion, up to eight rounds, so the deadline binds on a tools-enabled run at
either end.

**2026-09-17.** Both CPU subagent servers pass `--threads` from their CPU quota since 2026-09-11
([ADR-0004](../adr/ADR-0004-model-lineup.md)). That server under the same saturating load decodes
4.89 to 5.03 tok/s on one slot and 3.02 to 3.07 on each of two, so the deadline admits at least 7200
decoded tokens, about seven times the cap, and the cap binds first on a busy host too. The saturated
rate without `--threads`, about a seventh of the idle one, was host contention: the same slot
recovered to the idle rate within seconds of the load stopping. Method: one busy worker per host
core beside the server; rates off the server's own `timings`.

On the GPU placement the same pick decodes 115 to 148 tok/s alone, so the whole cap decodes in 7 to
9 s (2026-09-11, the constrained run above).
