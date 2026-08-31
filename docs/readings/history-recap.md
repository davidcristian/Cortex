# Readings: history recap

What one fold of the summarizing history window costs, what it keeps over repeated folds, and what
it costs under concurrent streams. Cited by [ADR-0038](../adr/ADR-0038-ranked-recall.md),
decisions 8, 9 and 20, and by [ADR-0014](../adr/ADR-0014-history-windowing.md) decision 6. The
corpus is one conversation written by the author of the feature, with the needed fact placed where a
summary would keep it, so these readings show the mechanism and are not a claim about real
conversations.

## One fold, bounded and unbounded

**2026-08-06.** A 23-message conversation whose first three exchanges contain the facts a later
question needs (a booking reference, a flight, a hotel, a card) and whose middle is filler, under a
character budget that pushes the opening out of the window, on the resident cortex (gemma-4-12B, 24
GB card). The identical fold prompt was sent with no bounds and with `RECAP_BOUNDS`:

| one fold | no bounds | `RECAP_BOUNDS` |
| --- | --- | --- |
| decoded tokens | 378, 531, 602 | 88, 87, 88 |
| wall time | 13.6 s, 18.9 s, 21.5 s | 3.9 s, 3.8 s, 3.9 s |
| account produced | 345 to 367 chars | 369 to 382 chars |

Unbounded, most of a fold is reasoning `drain_text` discards; one fold decoded 6,286 tokens for a
370-token prompt. The same prompt capped at 160 or 256 tokens with thinking left on returned an
empty reply, and at 512 it finished in some runs and not others, so the cap is paired with the
switch. Across staged five-fold runs a bounded fold decoded 61 to 163 tokens in 2.9 s to 6.2 s. A
cached read costs 0.000 s at three decimal places.

## What the account keeps

**2026-08-06.** Three independent sessions of five compounding folds each, fenced and bounded: the
booking reference survived into the final account and reached the reply 3 of 3 times, and the plain
window (the control) failed to answer 3 of 3 times. No fence marker reached a reply. Unbounded, the
same variant kept the reference 2 of 3 times. At the shipped floor of 2,000 characters the
conversation folded once over five boundary moves, for 3.4 s of model time, and 10 of the 20 dropped
messages sat under the floor, in neither the window nor the account. Behind the fence the recap
message is about twice the account's length (a 484-character account arrives as 1,022 characters),
and the reply was unchanged. Method: `packages/inference/tests/test_history_recap_live.py`,
integration-marked; retention is reported as a rate, not asserted.

## Folds under concurrent streams

**2026-08-08.** Three `Converse` streams started together on the shipped `converse` use case, each
on its own session forcing a fold, gemma-4-12B at a 16K context. Solo, a turn reached its first
token in 4.6 s with the fold holding the lease 2.4 s. Together:

| acquisition | asked | granted | released | waited |
| --- | --- | --- | --- | --- |
| s0 fold | 0.00 | 0.00 | 2.81 | 0.00 |
| s2 fold | 0.00 | 2.81 | 5.61 | 2.81 |
| s1 fold | 0.00 | 5.61 | 8.23 | 5.61 |
| s0 reply | 2.82 | 8.23 | 10.44 | 5.41 |
| s2 reply | 5.61 | 10.44 | 12.27 | 4.83 |
| s1 reply | 8.24 | 12.27 | 17.75 | 4.03 |

No two holds overlapped and within every stream the fold released before its reply acquired. Time
to first token rose to 10.3 s, 12.0 s and 17.5 s, and `s0`'s reply waited behind two other streams'
folds. Every stream answered with its own booking reference, twelve of twelve over four runs, and
each `folding` status reached only its own stream. Two concurrent turns of one session both folded
and both answered correctly; the surviving recap covered a prefix that exists (14 of 26 messages).

At a stream credit bound of one with the reader stalled 12 s, the stalled reply held the lease 16.52
s against 2.2 s to 3.6 s unstalled, and the next stream's fold waited 16.51 s. The shipped
`CORTEX_SEAM_CONVERSE_BUFFER` is 256, so at the default this needs a turn of more than 256 events.
Method: `packages/orchestrator/tests/test_fold_under_load_live.py`, integration-marked, five
variants, each lease timestamped at request, grant and release; the run fails when no acquisition
happened inside another stream's hold.
