# The recap measurement's single corpus

**Status:** done 2026-08-08
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The measurement behind the recap feature was one hand-built conversation, written by the author of
the feature, with the needed fact placed where a summary would keep it. It shows the mechanism
works; it is not a benchmark. Until the split below, the entry waited on a real conversation and on
anything about a cortex under load, before these numbers were quoted as evidence about either. Three
things it did not cover were recorded, and two were measured on 2026-08-06. Fold quality after
several boundary moves is the weak one: over three independent sessions of five folds each, the
opening fact survived into the final account 2 of 3 times, and the round that lost it lost the whole
opening (no reference, no hotel, no card) while keeping the recent filler. Repetition came back 3 of
3 with the control failing 3 of 3. Retention later moved to 3 of 3 over the same three staged
sessions once the fold was made cheap, which is what let the default move.

On 2026-08-08 the rest was split in two, because the two halves are not the same kind of
not-done. "A real conversation" is an objection about who wrote the corpus, and no run fixes that:
every corpus this repo can produce is written by the party whose conclusion it tests. It is
therefore a permanent caveat on these numbers rather than work, and it retires only through use,
when the shipped feature meets conversations nobody staged. "Anything about a cortex under load"
is about hardware and concurrency, the card is here, and a fold contending with a reply for one
non-reentrant lease is something a staged run can show.

That half was measured the same day by
`packages/orchestrator/tests/test_fold_under_load_live.py`: the shipped `converse` use case over
the real adapter, the real Redis store and the real resident cortex, with every model call's lease
timestamped at request, grant and release. The sequencing argument was checked against the tree
first and every clause still held: the lease is taken on the adapter generator's first
`__anext__` and held to the end of its `async with`, a fold takes it through `drain_text` which
leaves that block in a `finally`, and `handle_turn` awaits the whole of
`assemble_inference_messages` several statements before it first iterates the reply.

The run proves the streams really overlapped rather than assuming it: it collects every moment one
stream asked for the lease strictly inside a different stream's hold and fails when it finds none,
because concurrent streams that never contend produce a clean pass that means nothing. Three folds
were requested at the same instant and five acquisitions were issued under someone else's hold.
The argument held on every point: no two holds overlapped, every stream's fold released before
that stream's reply acquired, nothing was left ungranted or unreleased, and no answer or stored
recap contained another session's booking reference, twelve of twelve over four runs. What load
costs is queueing: time to first token went from 4.6 s solo to 10.3 s, 12.0 s and 17.5 s, and one
reply waited 5.41 s behind two folds that were not its own. Two turns of one session were also run
concurrently, since append-only history is why a racing pair of folds is safe: both answered with
the session's own reference and the surviving recap covered a prefix that really exists, the loser
of the write race paying a repeated fold rather than giving a wrong answer. The test itself was
shown able to fail first: a window that opens a model call and never closes it, which is what
`drain_text` prevents, deadlocked the turn and the same checker named it, and the same two streams
run one after the other reported zero contentions.

What is left is the authorship caveat above, which no run retires, and
[R-035](035-stalled-consumer-holds-lease.md).

## History

- 2026-08-06: Opened when the summarizing window shipped, recording that the run behind it was one
  hand-built conversation by the author of the feature.
- 2026-08-06: The re-run covered two of the three gaps. Fold quality after several boundary moves
  came back 2 of 3 over three sessions of five folds, and repetition came back 3 of 3 against a
  control failing 3 of 3.
- 2026-08-06: Retention moved to 3 of 3 over the same three staged sessions once the fold was made
  cheap, which is what let the default move; the corpus half was unanswered and the default moved
  anyway.
- 2026-08-08: Split into a permanent caveat about who wrote the corpus, which no corpus this repo
  can build retires, and one item, the fold under a cortex under load.
- 2026-08-08: The item closed the same day, by three overlapping `Converse` streams over the real
  cortex with every lease timestamped and the run failing unless the streams provably contended.
  The sequencing argument held on every point and the price is queueing. The run opened
  [R-035](035-stalled-consumer-holds-lease.md).
- 2026-08-08: The run's driver was committed in `packages/orchestrator/tests/` as an
  `integration`-marked test, which settled where a host-side client of the body and brain
  interface belongs. Because its subject is a lock inside the brain process it was driven
  in-process, so it restarted no container and reported no interval.
- 2026-08-09: One claim did not survive the next measurement. This run's corpus is conversation
  history through `RedisSessionStore`, while the recall measurement seeded 41 memory notes through
  `PgVectorMemoryStore` behind the CPU embedder and removed them with `delete_scope`, so the
  practice of seeding under test-owned ids transferred and the mechanism did not.
