# Readings: the age of a recalled memory, shown to the models

Whether the answer to a question about a fact that changed names its newest value, with recalled
memories shown as their text alone and with each memory's age shown beside its text, in both the
`judge` rank's numbered notes (`rerank_judge.py`) and the reply's memory list (`turn_context.py`).
The flows that found the defect are in
[the memory over time flows](overlay-memory-over-time-flows.md#one-value-replaced-twice).

## The rig

**2026-10-26**, the shared stack of that night (compose project `cortexn8`, its own volumes): the
cortex gemma-4-12B at a 16384 context on the GPU, Postgres with pgvector and the CPU embedder, the
default global memory scope and the default `judge` recall rank. A driver sent every row straight
to the brain over `Converse`, each in a new chat, so only memory joined them. The pool already held
36 memories about other facts.

## Rows and the pass rule, written before the first row

**Rows.** Twelve facts, none named by an earlier memory in the pool. Each fact is stated three
times, each time in a new chat, as "Please remember this: ..." with no word that marks a change.
The three stored exchanges are then dated 21, 9 and 2 days before the run in the `memories` table,
as a person who changes a fact over weeks would leave them. Each fact is then asked once in a new
chat ("What is my dog called? One word."). That is one pass of 12 rows. After a pass the memories
its questions wrote are deleted, so every pass starts from the same pool.

**A row passes** when the reply names the newest value and no older one. A reply naming no value,
or two, fails.

**Conditions**, each on the same stored pool, two passes (24 rows):

- **baseline**: the current build, each memory shown as its text alone.
- **relative**: each memory's text after its age in its largest whole unit, "(9 days ago)", in
  the rank's notes and the reply's list, and one sentence in each header: each memory starts with
  its age, and when two disagree the newer one is current.
- **date**: the same, with the date the memory was written in the user's zone, "(2026-10-17)", in
  place of the relative age.

**The rule.** A treatment ships when it passes at least 6 more of its 24 rows than the baseline
does. A gap of 3 to 5 is not separated from noise: the next step is a replication on twelve new
facts, and nothing ships. A gap under 3, or a treatment that passes fewer, declines it. When both
treatments clear the rule, the one with more passes ships, and on a tie the relative form, which
costs fewer tokens and needs no zone.

## The run

Of the 36 statements, 4 were not stored on the first try: the turn called
`list_allowed_directories`, and a turn that read untrusted content records no memory. Those four
were sent again in new chats before the dating, and each was stored, so every fact held its three
values. Each question pass deleted its 12 question memories afterwards, and the pool held 72
memories at the start of every pass. Before and after every pass the SM clock read 0.59 to 0.60
of the card's maximum (`clocks.sm` over `clocks.max.sm` in `nvidia-smi`).

| condition | pass 1 | pass 2 | rows passed |
| --- | --- | --- | --- |
| baseline | 3 of 12 | 4 of 12 | 7 of 24 |
| relative | 12 of 12 | 12 of 12 | 24 of 24 |
| date | 12 of 12 | 12 of 12 | 24 of 24 |

On the baseline, every failure named exactly one older value: dog, drink, flight and piano were
answered with the oldest value and locker, yoga, wifi and team with the middle one, in both passes,
and fruit with the middle one in the first. Both treatments named the newest value in
every row. The baseline's recall lines were not kept, since the brain container was recreated for
the treatment. In the 48 treatment recalls the rank kept all three values 47 times, the newest
first 46 times, and once (a date pass) kept only the newest. Where the rank put an older value
first (wifi in both relative passes), the reply still named the newest.

The mean question row took 0.89 times the baseline's time on the relative build and 1.02 times on
the date build, which is within the spread of single rows.

## What a date costs

Counted with the cortex's own `/tokenize` on the shared stack:

| form | tokens per memory |
| --- | --- |
| `(3 days ago) ` | 6 |
| `(21 days ago) ` | 7 |
| `(just now) ` | 5 |
| `(2026-10-23) ` | 13 |
| `(2026-10-23 14:05) ` | 19 |

The header sentence adds 20 tokens to the reply's memory list and 22 to the rank's instruction.
With the default `k` of 5 and pool factor 4, the rank reads up to 20 notes, so the relative form
adds about 150 tokens to a rank request and about 55 to a turn's memory list, against about 280
and 85 for a date. The relative form needs no zone, since it is computed from elapsed time.

## Result

Both treatments cleared the rule by 17 rows, and they tied, so the relative form ships: each
trusted memory in the reply's list and each note in the rank's list starts with its age
(`memory_age.py`), and both headers say the newer of two disagreeing memories is current. A fenced
memory shows no age, so the line before each fence is still the one that says the text is data.
Not measured: the age without the header sentence, and the `reranked` rank on the baseline build.

## Each memory's text on one line

**2026-10-26**, the same rig and the same 36-memory pool, on a change that shows every note of the
rank and every fenced memory with its line breaks replaced by spaces (`one_line` in
`memory_age.py`), so a tainted memory's text cannot start a line that reads as another note with a
newer age. Every stored exchange has a line break between its `User:` and `Assistant:` parts, so
every note the rank reads changed. A trusted memory in the reply's list keeps its lines.

**The rule, written before the first row.** The same twelve facts and 36 statements, dated as
above; two question passes on the build before the change, then the brain rebuilt from the tree,
then two passes after it. The change ships unless the after build passes at least 3 fewer of its
24 rows than the before build; a drop of 3 or more holds it and calls for a replication on twelve
new facts.

**The run.** 7 of the 36 statements were not stored on the first try, since each turn called
`list_allowed_directories` and so read untrusted content; each was sent again in a new chat and
stored. Before and after every pass the SM clock read 0.59 to 0.60 of the card's maximum.

| build | pass 1 | pass 2 | rows passed |
| --- | --- | --- | --- |
| before the change | 12 of 12 | 12 of 12 | 24 of 24 |
| each memory on one line | 12 of 12 | 12 of 12 | 24 of 24 |

In all 48 recalls the rank put the newest value first. It kept all three values in 20 of the 24
recalls before the change and in 22 of the 24 after it; every other recall kept the newest value
and dropped one or both older ones. The change passed the rule and ships.

Method: the drivers (`drive.py`, `backdate.py`, `score.py`, `kept.py`) are in the run's scratch
directory, not in the tree.
