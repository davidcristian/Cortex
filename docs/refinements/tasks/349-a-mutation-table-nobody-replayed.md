# Every mutation table in the record is the hand that wrote it reporting on itself

**Status:** landed 2026-08-21
**Area:** cross-cutting
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Opened 2026-08-20 by a review of a run of fourteen changes landed in one sitting, and it is about
the review as much as about the changes. Most of those commit bodies end in a mutation table: this
edit reddens five cases, that one reddens 27. The tables are the repo's own answer to distrusting
green and they are the most valuable sentence in each message. Not one of them was re-run by
anybody other than the agent that wrote it.

**What that means precisely.** A mutation count is a claim of the form "the suite would have caught
this", and the evidence for it is a run nobody else observed, on a working tree nobody else has. The
tree that survives is the unmutated one, so the claim is unfalsifiable after the fact without
redoing the work: reconstructing the mutation from the sentence describing it, applying it, and
running the suite. Where the sentence is precise that is minutes. Where it says something like
"reverting the way out reddens six" it is a reading exercise first. Two of the run's messages state
that every mutation was read back off disk before its result was trusted, which is the discipline
this depends on and is itself a self report; the review that opened this entry was told, and did
not measure, that at least one table in the run had first been trusted off an edit that landed on
the wrong lines. That is recorded here as reported rather than as measured, and it is the exact
failure this entry names.

**The measurements have the same shape and a worse one.** The Docker dependent figures in the same
run, the log driver's 16 KiB cliff and the character counts on the recall trail, were produced by
one agent against containers that no longer exist. A number nobody re-measured is not wrong, but it
is a number whose only evidence is a paragraph, and the two paragraphs above it in the same message
are argument rather than evidence.

**Why this is not an argument for less of it.** Recording a mutation table is strictly better than
not recording one, and nothing here suggests dropping the practice. The gap is that the practice has
no second reader, so it inherits the weakness of every self report: the honest agent and the
mistaken one produce the same paragraph.

**What would close it.** A mutation table written so that it can be replayed without judgement,
naming the file, the exact edit and the expected count, and a pass that replays a sample of them
from the record. The replay is mechanical and could be a script over the messages that carry the
tables, which is a smaller thing than it sounds: the tables already follow one shape. The decision
this entry actually asks for is whether replayability is a requirement of the table's wording or a
practice of whoever reviews, because the first is enforceable and the second is not.

## Trail

- 2026-08-20: opened by a close-out review of a fourteen commit run, which found every mutation
  count and every container measurement in it resting on a single unrepeated observation by the
  agent that authored the change.
- 2026-08-21: **replayed, then decided.** Five tables were replayed out of the record, thirty two
  stated rows over forty nine runs, each mutation applied in a scratch worktree and reverted with a
  byte for byte comparison against the pre-mutation file. **Every row reproduced.** The deadline
  clamp table (three constants over seven cases, claiming 4, 4, 4) gave 4, 4, 4, and its paired
  claim that all three passed the case as it stood before holds. The credential withholding table
  (five rows claiming one, the same one, six, one, six) gave 1, 1, 6, 1, 6, each named case being
  the one named. The named turn table (5, 5, 3, 27, 1) gave 5, 5, 3, 27, 1 over the whole brain
  suite at 2,786 cases. The heading gate table (fourteen mutations against both the suite it
  replaced and the suite it landed) gave 41 passed on all fourteen before and, after, twelve
  reddening one case and the two on the shared remedy reddening six. The compose default survey's
  twenty six planted drifts and its suite guard were sampled five ways, and all five behaved
  exactly as written, `found 1, pinned 2` included.
  What varied was cost rather than correctness: four minutes where the table names the file, the
  edit and the suite, fifteen where it names none of the three. The file and the edit came off the
  commit's own diff in every case, because a mutation is always a perturbation of a line the change
  itself touched; **the suite is the one fact the diff does not carry**, so that is what AGENTS.md
  now requires a table to name, as a rule no machine checks. The enforceable form was refused on a
  measurement: over 561 commits, 100 bodies carry the vocabulary and 88 name no tracked path, only
  54 use `reddens` at all, and one of the 100 is a change whose body correctly says it carries no
  table. The script over the messages was refused with it, the census being thirty lines against
  forty minutes of replay. Both doubted measurements were re-taken: the log driver's cliff holds
  exactly on Docker 29.1.3 with `json-file`, and the recall trail's 1,458 to 1,475 came back 1,458
  to 1,476 on a fresh 200 draws. **This entry was wrong about the second one's shape**: it needs no
  container, being a synthesis over drawn ids and scores, which is why it cost two minutes.
  Recorded in the ADR-0002 replay addendum. Opened by this close:
  [R-357](357-a-replay-pass-has-no-cadence.md),
  [R-358](358-the-widest-value-was-never-a-real-line.md) and
  [R-359](359-the-table-detector-is-refused-not-impossible.md).
