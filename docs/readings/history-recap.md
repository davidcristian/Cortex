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

## A message cut by the fold

**2026-10-15**, the cortex (gemma-4-12B, `--ctx-size 16384`, the server's sampling at temperature
1.0) on the 24 GB card. One fold reads at most `RECAP_READ_MAX` (16,000) characters, and a longer
first message is cut. Each row is a fold prompt from `build_recap_messages` sent straight to the
cortex server with `RECAP_BOUNDS`, drawn four times per variant.

Rows. Each C row is a pasted message whose unread part contradicts the read part; each N row is cut
by nothing, so a fix must leave its recap as good as before.

- **C1**: the 60,175-character log from the flow above plus the question about its last line. The
  read part is all `status=200`; the last line is a `status=503` error.
- **C2**: the 22,206-character log of the same kind, ending with the same kind of error line.
- **C3**: 30,000 characters of planning notes that set the launch for Tuesday 3 November, then a
  last line moving it to Thursday 12 November, plus "When is the launch?".
- **N1**: an uncut chat of four exchanges holding a lock code and place, a sister's arrival date and
  time, a restaurant decision and an open question.
- **N2**: a 15,207-character log (under the limit) ending with an error line, plus the question.

Variants. **B**: the tree. **I**: the cut line reworded as a fact ("The remaining N characters of this
message were cut here and were not read."), nothing else changed, so an uncut fold is unchanged.
**I2**: the tree's cut line plus one instruction sentence saying a bracketed cut line marks text
never seen, that the account says the message was cut, and states nothing about the unread part.
**H**: the message's first 12,000 and last 4,000 characters around a line naming the middle cut,
with I2's sentence. N rows are drawn for B, I2 and H only, since I sends them byte for byte as B.

Pass rule, written before the baseline. A C recap passes when it says the message was cut or only
partly read, and states nothing about the unread part as fact: no "all 200", "no errors" or the like
about the whole log, and no claim that 3 November is the final launch date. A recap from variant H that
reports the error line or the 12 November move as read passes that half. An N1 recap passes when it
keeps 4729, the east door, 23 October, Lindenhof and the open travel choice, and claims no cut; an N2
recap passes when it names the `503` error and claims no cut. A recap that `clean_recap` rejects
fails. An variant ships when it passes at least 10 of its 12 C recaps, B passes at most 6 of 12, and
its N passes are no fewer than B's. Between two variants that both ship, the one with more C passes
wins, and on a tie the smaller change (I, then I2, then H).

The first draw, scored by hand against that rule (four recaps per row and variant; C out of 12, N out of
8):

| Variant | C1 | C2 | C3 | C passes | N passes |
| --- | --- | --- | --- | --- | --- |
| B | 0 | 1 | 0 | 1 | 8 |
| I | 0 | 1 | 1 | 2 | 8 (same prompts as B) |
| I2 | 3 | 4 | 0 | 7 | 6 |
| H | 1 | 0 | 3 | 4 | 7 |

No variant ships. B's C1 and C2 recaps call every request 200; ten of B's, I's and I2's twelve C3 folds
listed item numbers until `clean_recap` rejected them. I2's two N misses claimed a cut in an uncut
fold. H's recaps were never wrong about the end: all eight C1 and C2 recaps reported the last line's
error, seven with its `503`, but seven answered the user's question without saying the message was cut, which the
rule requires; its N miss named the error without its code.

Second rule, written after the first draw and before the second. A C recap passes when
`clean_recap` accepts it and it states nothing false about the message as a whole: "all 200", "no
errors" or the like passes only when scoped to the part read or shown, a recap reporting the last
line's `503` or the 12 November move passes, and one giving 3 November as the launch date with
neither the move nor a cut fails. Variant **H0** is H without the instruction sentence, so an uncut fold
is sent byte for byte as B's and no N row is drawn. B and H0 are drawn six times per C row; H0
ships when it passes at least 15 of its 18 and B at most 9 of 18.

The second draw, scored against the second rule (six recaps per row and variant, out of 18):

| Variant | C1 | C2 | C3 | C passes |
| --- | --- | --- | --- | --- |
| B | 4 | 2 | 3 | 9 |
| H0 | 6 | 6 | 6 | 18 |

H0 ships. Every H0 log recap gave the last line's request id and `503`, and every C3 recap gave the
move to 12 November; none was rejected. B's misses gave every request as 200, or gave the read
part's time range as the whole log's, with no cut named; three of its scores are close calls (C1's
fourth recap called the log a snippet and passed; C2's fourth named only a truncated last entry and
its fifth gave the range unscoped, and both failed). Three of B's C3 folds were rejected. Most H0 recaps answer the question that follows the
paste rather than describe the log, which the head-only cut never showed the fold. The shipped
`fold_slice` keeps the first 12,000 and last 4,000 characters around the line H0 sent, and an uncut
fold is unchanged. Method: `measurements/overlay-long-input-2026-10-15/recap-cut/` (`draw.py`,
`show.py` and the three `.jsonl` files of recaps); the SM clock read 0.58 of its maximum.

## A rejected fold over a list

**2026-10-15**, the same cortex, through the real Linux shell. A 53,836-character inventory (860
lines, each naming an item number, an owner, a bin and two counts) was pasted into a new chat, and
four one-word questions followed. The first reply is the note that the message is longer than the
context; the paste then drops out of the window and is folded on turn 2. The brain ran the change
that stores a note of the gap when a fold is rejected.

- With "Which bin is item 4958 in?" after the list (session `ba92ba85`), the fold was accepted and
  stored "Item 4958 is in bin B-34.", which answers the question and keeps nothing else of the list.
- With the list followed by one word and no question (session `7ced67a2`), the 512-token bound
  stopped the fold at 1,121 characters of entries and `clean_recap` rejected it. The brain logged
  one warning, with `capped=True`, and stored `UNFOLDED_NOTE` with `covers` 1; turns 3 to 5 sent no
  fold and logged no warning. Before the change nothing was stored, so each later turn would have
  folded the same paste again.

Method: `measurements/overlay-long-input-2026-10-15/list-fold/` (`genlist.py`, `flow.sh` and both
flow logs).
