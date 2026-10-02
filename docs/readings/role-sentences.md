# Role sentences

What the sentence of each shipped subagent role ([ADR-0072](../adr/ADR-0072-subagent-roles.md)) does
to delivery on the constrained path. The harness, the report bodies, the judge and the terms are
those of [reply envelope](reply-envelope.md): "delivered" is read by `delivered` in
`scripts/envelopejudges.py` at the tabled reading, a "copy" is the report body handed back, and
intervals are Wilson 95%. Every cell is four report bodies at eight seeded draws, or sixteen where
its entry says so, drawn by `brain/packages/orchestrator/tests/test_envelope_cost_live.py` through
`CORTEX_ENVELOPE_INSTRUCTION`.
Every run is the shipped constrained path. The role column appends the matching `SHIPPED_ROLES`
sentence to the shape's instruction, as `SubagentRole.applied` does, so it comes ahead of
`REPLY_INSTRUCTION`. "Channel writes" counts runs with any text in the reasoning channel, which a
delegated run drops. At one build a seeded draw returns the same reply, so a cell drawn again at the
same seeds repeats the first draw rather than sampling again; a new seed base samples again.

## The default pick on CPU

**2026-09-29**, gemma-4-E4B on CPU while another run held the card: `ghcr.io/ggml-org/llama.cpp:server`
at `sha256:db057ec90de0`, `build_info` `b10680-d7bd3bfca`, under `docker --cpuset-cpus 12-23`, with
`-ngl 0 --jinja`, the reasoning-off pair, `--cache-ram 0`, `--ctx-size 16384 --parallel 4` (4096
tokens a slot, as the compose file's 8192 over 2) and `--threads 12`. Up to twelve harness processes
shared the four slots. The `precis` sentence then read "Reply with the text you were given made
shorter, keeping every figure, name and date it states and adding nothing it does not state." The
`excerpt` sentence, drawn in every row here and no longer shipped, read "Reply with each item the
subtask asks for, written exactly as the text you were given writes it, one per line, and nothing
else." Written before the first row: a role changes delivery only where the two intervals do not overlap,
and the `excerpt` sentence conflicts with `REPLY_INSTRUCTION` only if the extraction copies with it
and not without it. Samples are under `measurements/envelope-roles-2026-09-29/`.

| shape | role | without | with | copies | cap refusals | channel writes |
| --- | --- | --- | --- | --- | --- | --- |
| summarization, its figures | `precis` | 25/32 (0.61 to 0.89) | **13/32 (0.26 to 0.58)** | 0, 6 | 7, 13 | 12, 15 |
| extraction | `excerpt` | 30/32 (0.80 to 0.98) | 26/32 (0.65 to 0.91) | 0, 0 | 2, 5 | 2, 6 |
| lookup | `answer` | 31/32 (0.84 to 0.99) | 30/32 (0.80 to 0.98) | 0, 0 | 1, 1 | 2, 3 |

The pairs read without, then with. The `excerpt` and `answer` sentences read inside the plain
column's interval, and no extraction copied, so the two sentences are not shown to change delivery
and `excerpt` does not conflict with `REPLY_INSTRUCTION` on this pick. The `precis` sentence reads
apart and lower: 6 of its 19 non-deliveries hand the body back `ok=True`, 5 of them on the network
body, and 13 stop at the cap. Its replication on the card, written down before it was drawn, is
the first row of the next section. The CPU columns are not comparable with the card columns: the same
plain shapes wrote into the channel on 16 of 96 runs here.

## The default pick on the card

Every row here is gemma-4-E4B at the compose file's argv with `-ngl 99` (`--jinja`, the
reasoning-off pair, `--cache-ram 0 --ctx-size 8192 --parallel 2 --threads 4`),
`ghcr.io/ggml-org/llama.cpp:server-cuda` at `sha256:952424b09abc`, `build_info` `b10680-d7bd3bfca`,
the build of the CPU row, drawn by an unattended run with its cells in one server session. The SM
clock is read from that run's sampler as a fraction of `clocks.max.sm`. The shape is the
figures-keeping summarization, "Summarize the report below, keeping its figures", constrained.

**2026-09-30**, the first `precis` sentence, seeds 1 to 8, without and then with it. SM clock 0.68
to 0.77 over the row's 19 samples, 0.73 at the median, with the software power cap active on
17. Counted as the CPU row was, the same count over the CPU samples reproduces that row cell for
cell. The rule: it replicates if the role column is
again lower with the two intervals apart. Samples and log: row `755` under
`measurements/sitting-2026-09-30/`.

| sentence | delivered | copies | cap refusals | channel writes |
| --- | --- | --- | --- | --- |
| none | 27/32 (0.68 to 0.93) | 0 | 5 | 9 |
| the first | **12/32 (0.23 to 0.55)** | 7 | 13 | 17 |

The intervals are apart again, so the drop replicates on the card. The plain cell reads within one
run of the card's shipped-wording reading of 2026-09-13, 26 of 32. With the sentence, 7 runs hand the
body back `ok=True`, 3 of them on the network body, and the 13 cap refusals fall on the other three
bodies.

**2026-09-30**, a rewording, written down before it was drawn: "Reply with a shorter version that
keeps every figure, name and date and adds nothing the text does not state.", which does not name
the given text as the reply that `REPLY_INSTRUCTION` then forbids. Seeds 1 to 8, three cells: no
sentence, the rewording, and the first sentence. SM clock 0.66 to 0.74 over the 27 samples taken
while it drew, 0.73 at the median, power cap active on 22. The rule: the rewording ships if its
interval overlaps the plain cell's. Samples and log: row `758` under
`measurements/sitting-2026-09-30b/`.

| sentence | delivered | copies | cap refusals | channel writes |
| --- | --- | --- | --- | --- |
| none | 27/32 (0.68 to 0.93) | 0 | 5 | 9 |
| the rewording | 20/32 (0.45 to 0.77) | 4 | 8 | 11 |
| the first | 12/32 (0.23 to 0.55) | 7 | 13 | 17 |

The rewording's interval overlaps the plain cell's, so by the rule it is the shipped `precis`
sentence. It reads 7 runs below the plain cell and 8 above the sentence it replaces, and still
hands the body back `ok=True` on 4 runs, 3 of them on the network body. The other two cells repeat
row `755` reply for reply, 32 of 32 each.

**2026-09-30**, the shipped rewording on a second seed base, seeds 9 to 16, the plain cell and the
rewording, read from the `SHIPPED_ROLES` of the tree the run was launched from. SM clock 0.65 to
0.77 over the 18 samples taken while it drew, 0.73 at the median, power cap active on 16, the
enforced limit between 0.80 and 0.89 of `power.max_limit`. The rule, written before the draw: the
rewording stays if its interval overlaps the plain cell's; apart and lower, the role gets no
sentence. Samples and log: row `760` under `measurements/sitting-2026-09-30c/`.

| sentence | delivered | copies | cap refusals | channel writes |
| --- | --- | --- | --- | --- |
| none | 23/32 (0.55 to 0.84) | 0 | 9 | 11 |
| the rewording | 16/32 (0.34 to 0.66) | 7 | 9 | 12 |

The intervals overlap, so by the rule the rewording stays shipped. It reads 7 runs below the plain
cell, as on the first seed base, and every copy is the body handed back `ok=True`, 5 of them on the
network body; the cap refusals are level. Over both seed bases the rewording delivers 36 of 64
(0.44 to 0.68) against 50 of 64 (0.67 to 0.87) plain, with 11 copies against none. That pooled count
was not written down before either row, so it decides nothing; the next row's rule is
[R-760](../refinements/tasks/760-the-reworded-precis-sentence-reads-below-the-plain-summary.md).

**2026-10-01**, the shipped rewording on a third seed base at twice the draws, seeds 17 to 32 at
sixteen draws a body, the plain cell and the rewording in one server session, the sentence read from
the `SHIPPED_ROLES` of the tree the run was launched from. SM clock 0.66 to 0.75 over the 34
samples taken while it drew, 0.73 at the median, power cap active on 33, the enforced limit between
0.80 and 0.91 of `power.max_limit`. The rule, written before the draw: Fisher's exact test, two-sided,
on the two counts of 64; where p is below 0.05 and the rewording reads lower, the role gets no
sentence, and otherwise the rewording stays. Samples and log: row `760s17` under
`measurements/sitting-2026-10-01/`.

| sentence | delivered | copies | cap refusals | channel writes |
| --- | --- | --- | --- | --- |
| none | 44/64 (0.57 to 0.79) | 1 | 18 | 19 |
| the rewording | 32/64 (0.38 to 0.62) | 13 | 19 | 27 |

Fisher's exact test gives p = 0.047, two-sided, and the rewording reads lower, so by the rule it
lowers delivery on this pick and `precis` ships with no sentence. The result rests on one run: 43
against 32, or 44 against 33, gives p = 0.07. Read by hand, every count above matches the replies.
The plain cell's 20 misses are the 18 cap refusals, one reply that is the report's title alone, and
one copy, the network body lightly reworded, the first copy a plain cell on this pick has returned
in this record. The rewording's 32 misses are the 19 cap refusals and 13 copies, every one handed
back `ok=True`: 4 on the clinic body, 4 on the fleet body and 5 on the network body, 4 of them the
body letter for letter. Every cap refusal also wrote into the channel, and 15 and 16 of them left
an empty reply.

Named by no rule, so they decide nothing: the cap refusals differ by one, and the rewording returns
12 more copies, the size of the gap between the cells. Over the three seed bases the rewording
delivers 68 of 128 (0.45 to 0.62) against 94 of 128 (0.65 to 0.80) plain, with 24 copies against
one; Fisher's test on those would give p = 0.001.

## The roster alternate on the card

**2026-09-30**, Qwen3.5-2B: the `llama-subagent-qwen` argv at `-ngl 99`, the image and build above,
each shape at four bodies and seeds 1 to 8, seven cells in one server session, row `755q` under
`measurements/sitting-2026-09-30b/`. The `precis` cell drew the first sentence, still shipped in the
tree the row ran from, and the rewording cell the one shipped now. SM clock 0.65 to 0.70 over
15 samples, 0.67 at the median, power cap active on 14. The rule: a role changes delivery here only
where its interval and the plain cell's do not overlap.

| shape | sentence | without | with | copies | cap refusals |
| --- | --- | --- | --- | --- | --- |
| summarization, its figures | `precis`, the first | 31/32 (0.84 to 0.99) | **9/32 (0.16 to 0.45)** | 1, 21 | 0, 1 |
| summarization, its figures | `precis`, the rewording | the same cell | **17/32 (0.36 to 0.69)** | 1, 14 | 0, 1 |
| extraction | `excerpt` | 27/32 (0.68 to 0.93) | **10/32 (0.18 to 0.49)** | 0, 0 | 5, 8 |
| lookup | `answer` | 24/32 (0.58 to 0.87) | 30/32 (0.80 to 0.98) | 0, 0 | 0, 0 |

Both `precis` sentences and `excerpt` read apart and lower here, `answer` inside the plain interval.
The plain cells repeat the 2B's shipped-wording column of [reply envelope](reply-envelope.md) reply
for reply. No run wrote into the channel, and every copy is the body handed back `ok=True`. Under
`excerpt` 8 runs stop at the cap repeating numbers; of 14 others not delivered, 6 give one number
and 4 write the sentence back.

**2026-09-30**, the same argv, image and build on a second seed base, seeds 9 to 16, four cells in
one server session: figures `none` and the shipped `precis` sentence, extract `none` and `excerpt`,
each sentence read from the `SHIPPED_ROLES` of the tree the run was launched from. SM clock 0.61 to
0.69 over the 11 samples taken while it drew, 0.67 at the median, power cap active on 6, the
enforced limit between 0.80 and 0.88 of `power.max_limit`. The rule, written before the draw: a
sentence's drop replicates where its interval is again apart from and lower than the plain cell's;
an overlap leaves the first row as one seed base's result and the sentence shipped. Samples and log:
row `761` under `measurements/sitting-2026-09-30c/`.

| shape | sentence | without | with | copies | cap refusals |
| --- | --- | --- | --- | --- | --- |
| summarization, its figures | `precis`, the rewording | 27/32 (0.68 to 0.93) | 23/32 (0.55 to 0.84) | 5, 8 | 0, 1 |
| extraction | `excerpt` | 22/32 (0.51 to 0.82) | **8/32 (0.13 to 0.42)** | 0, 3 | 5, 5 |

The `excerpt` drop replicates: its interval is apart and lower again. The `precis` rewording reads
inside the plain interval, so its first reading stays one seed base's result. No run wrote into the
channel, and every copy is the body handed back `ok=True`. Under `excerpt`, of the 24 extractions
not delivered, 5 stop at the cap, 4 of them repeating numbers, 3 hand the body back, 10 write the
instructions back, 9 of them the role sentence, 2 give one number, and 4 describe or announce a
reply instead of giving it.
