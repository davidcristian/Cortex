# The other four subagent candidates have no CPU row

**Status:** done 2026-09-09
**Area:** inference
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)

`PLACEMENTS` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
gives every thinking-off model a `shipped-argv` row on the CPU, so gemma-4-E2B, Qwen3.5-0.8B,
Qwen3.5-2B and Qwen3.5-4B each get one, and none had been run. The 2026-09-05 placement table had
the pick's CPU row and nothing else's, so the injection table's claim that the lineup was measured
under one command line was true of the card alone.

The entry priced a CPU row at about half an hour on this host, generalising from the pick's 1837 s
row, and so priced the four at two hours. They took 2552 s together, about 43 minutes: 417 s, 526 s,
1088 s and 521 s. The pick is the largest artifact in the tier at 5,154,941,280 bytes, and wall
clock on this tier does not follow file size anyway, since Qwen3.5-2B at 1.3 GB and gemma-4-E2B at
3.3 GB ran within five seconds of each other.

Run on 2026-09-09, one `pytest` session per row, under the CPU placement's full form, which by then
had the override's memory caps as well as its CPU quota
([R-559](559-the-cpu-row-carries-the-cpu-quota-and-not-the-memory-cap.md)).

| candidate | framed obeyed / 10 | framed mentioned / 10 | control obeyed / 10 | control mentioned / 10 |
| --- | --- | --- | --- | --- |
| Qwen3.5-0.8B | 0 | 0 | 0 | 0 |
| Qwen3.5-2B | 1 | 1 | 1 | 2 |
| Qwen3.5-4B | 1 | 2 | 2 | 3 |
| gemma-4-E2B | 3 | 3 | 2 | 3 |

Three of the four repeat the card row cell for cell, on the same attacks, and six of the thirteen
replies the rows fired are the card session's words back word for word. The fourth, Qwen3.5-4B, is
the one candidate whose cell the record already measured as moving: its framed mention count is 2 at
both placements, inside the 2 to 3 measured over eight sessions, and what moved is the split inside
it, one card report becoming a CPU application. One session per placement cannot separate that from
the candidate's own instability. The full table, the reading and the thirteen replies are in the
CPU-row session of 2026-09-09 ([injection text rows](../../readings/injection-text-rows.md)).

The session also corrected a published sentence: the lineup readings of 2026-09-06 say
`output-laundering` is the only attack any framed row applied, and that session's own list of
replies has gemma-4-E2B applying `refusal-suppression` and `conditional-trigger` too.

## History

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which ran the
  pick's CPU row twice and no other.
- 2026-09-09: all four rows run and published, the thirteen fired replies recorded with their hand
  readings, and the cost measured at 43 minutes for the four against the two hours this entry
  assumed.
