# The recap measurement's single corpus

**Status:** landed 2026-08-08
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

**The measurement is one corpus, and half of what it did not measure has now been measured
(2026-08-06).** It shows the mechanism works rather than serving as a benchmark: a single hand-built
conversation, by the author of the feature, with the needed fact placed where a summary would
keep it. Two of the three things it did not cover were taken on the re-run below. **Fold quality
after several boundary moves is no longer unmeasured, and it is the weak one:** over three
independent sessions of five folds each, the opening fact survived into the final account 2 of 3
times, the round that lost it losing the whole opening (no reference, no hotel, no card) while
keeping the recent filler. **Repetition is covered too**, the single-fold arm having answered 3
of 3 with the control failing 3 of 3. What is still one corpus is the conversation itself: still
hand-built, still by the author, still with the fact placed where a summary would keep it, and
still nothing about a cortex under load. **The retention half of that trigger was answered
2026-08-06** and is now 3 of 3 over the same three staged sessions (the cheap-fold entry below),
which is what let the default move; the corpus half was not, and the default moved anyway.
**Trigger:** now the standing one, since the feature ships on: a real conversation, and anything
about a cortex under load, before this measurement is quoted as evidence about either.
**Split 2026-08-08 into a caveat and an item, because the two halves of that trigger are not the
same kind of not-done.** "A real conversation" is an **authorship** objection, and authorship is
not something a run can fix: every corpus this repo can produce is written by the party whose
conclusion it tests, so a wider or more adversarial one moves the evidence and never the caveat.
It is therefore recorded here as a **permanent caveat** on these numbers rather than carried as
work, and it retires only through use, when the shipped feature meets conversations nobody staged.
"Anything about a cortex under load" is a different claim entirely: it is about hardware and
concurrency, the card is here, and a fold contending with a reply for one non-reentrant lease is
exactly the kind of thing a staged run can show. **That half stays the area's one open item**, and
it is what the count means now. Nothing about the measured results changes; what changes is that
the entry stops asking for a corpus that would not settle it.

**The cortex-under-load half was measured 2026-08-08 and the sequencing argument held
([ADR-0038 fold-under-load addendum](../../adr/ADR-0038-ranked-recall.md)); this entry closes and
its authorship half stays a caveat.** The entry above split into a caveat and an item that
morning, and the item said nothing had been measured about a fold contending with a reply for
one non-reentrant lease. It has been, by
`packages/orchestrator/tests/test_fold_under_load_live.py`: the shipped `converse` use case over
the real adapter, the real Redis store and the real resident cortex, with every model call's
lease timestamped at request, grant and release. **The argument re-derived first, since this
file's own warning demands it**, and every clause of it still matched the tree: the lease is
taken on the adapter generator's first `__anext__` and held to the end of its `async with`, a
fold takes it through `drain_text` which leaves that block in a `finally`, and `handle_turn`
awaits the whole of `assemble_inference_messages` several statements before it first iterates the
reply. **What was proven, rather than assumed, is that the streams overlapped**: the run collects
every moment one stream asked for the lease strictly inside a different stream's hold and fails
when it finds none, because concurrent streams that never really contend produce a clean pass
that means nothing, which is the null result this backlog has recorded twice. Three folds were
requested at the same instant and five acquisitions were issued under someone else's hold. **The
argument held on every point it claims**: no two holds ever overlapped, every stream's fold
released before that stream's reply acquired, nothing was left ungranted or unreleased, and no
answer or stored recap carried another session's booking reference (twelve of twelve over four
runs, one window instance shared by all three streams, one `folding` chip landing on each
stream's own wire). **What load costs is queueing**: time to first token went from 4.6 s solo to 10.3 s,
12.0 s and 17.5 s, and one reply waited 5.41 s behind two folds that were not its own, which is
the interleaving the argument never denied and nobody had priced. Two turns of ONE session
concurrently were run too, since append-only history is the whole reason a racing pair of folds
is safe: both answered with the session's own reference and the surviving recap covered a prefix
that really exists, the loser of the write race costing a repeated fold and never a wrong answer.
**The harness was proven able to fail before it was trusted**: a window that opens a model call
and never closes it, which is exactly what `drain_text` prevents, deadlocked the turn and the
same checker named it (`fold took the lease and never released it`, `reply waited for the lease
and never got it`), and the same two streams run one after the other reported zero contentions.
Remaining from this deferral: the stalled-consumer entry below, and the corpus caveat above,
which no run retires.

## Trail

- 2026-08-06: Opened when the summarizing window landed, recording that the run behind it was one
  hand-built conversation by the author of the feature, with the needed fact placed where a
  summary would keep it.
- 2026-08-06: The re-run took two of the three things it had not covered. Fold quality after
  several boundary moves came back 2 of 3 over three sessions of five folds, and repetition came
  back 3 of 3 against a control failing 3 of 3.
- 2026-08-06: The retention half moved to 3 of 3 over the same three staged sessions once the fold
  was made cheap, which is what let the default move; the corpus half was unanswered and the
  default moved anyway.
- 2026-08-08: Restated and split into a permanent authorship caveat, which no corpus this repo can
  build retires, and one item, the fold under a cortex under load.
- 2026-08-08: The item closed the same day, by three overlapping `Converse` streams over the real
  cortex with every lease timestamped and the run failing unless the streams provably
  contended. The sequencing argument held on every point and the price is queueing, one reply
  waiting 5.41 s behind two folds that were not its own. The run opened one entry, a stalled
  consumer holding the lease for its whole reply, which sits in the fix-when-it-bites bucket.
- 2026-08-08: The run's driver landed in `packages/orchestrator/tests/` as a committed
  `integration`-marked test, which was recorded as settling by a second instance where a host-side
  client of the seam belongs, and as settling seeding a corpus into a session scope under
  test-owned ids. Because its subject is a lock inside the brain process it was driven in-process
  rather than across the wire, so it restarted no container between arms and reported no interval.
- 2026-08-09: The seeding half of that claim did not survive the next measurement. This run's
  corpus is conversation history through `RedisSessionStore`, while the recall harness seeded 41
  memory notes through `PgVectorMemoryStore` behind the CPU embedder and removed them with
  `delete_scope`, so the discipline of seeding under test-owned ids carried over and the mechanism
  did not.
