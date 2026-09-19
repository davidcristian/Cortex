# The field's upper bound assumes the shipped id factory

**Status:** done 2026-09-15
**Area:** memory
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

The recall trail's `dropped` field at the shipped pool of twenty renders as 1,101 characters of
syntax and id plus twenty float reprs, and no Python float renders in more than 24 characters, so
the field cannot pass 1,581 however the cosines fall. The 1,101 is where the assumption lives: it
is twenty ids at 36 characters each plus the JSON around them, and 36 is what `str(uuid4())`
produces.

`MemoryRecaller` takes `id_factory` as a constructor argument so it can be swapped, and the
composition root passes none, so the shipped brain mints uuid4 and the bound holds. A deployment
that injects a longer factory moves the field's width by twenty characters for every character it
adds to an id, and nothing compares the result with `VALUE_CHARS`. At the shipped bound the slack
is 467 characters, which buys 23 characters of id: at 60 characters the worst case passes 2,048 and
at 65 the measured reprs do, and a cut trail line is the failure the bound was sized to avoid.

Either a bound on the id at the port, which is a real constraint on a field the store round-trips,
or a line in `docs/modules/brain-memory.md` naming 60 as the id width at which the trail starts
losing candidates. The second is the cheap one and probably the right one: the id is the store's
identity, and narrowing it to buy log headroom would let a logging bound dictate a storage
identity.

## History

- 2026-08-26: opened by the close of
  [R-358](358-the-widest-value-was-never-a-real-line.md), whose strongest result is an arithmetic
  bound rather than a sample.
- 2026-09-10: neither half of the trigger has fired. `MemoryRecaller.__init__` still defaults
  `id_factory` to `_uuid4_memory_id`, which returns `str(uuid4())`, and the one construction in
  `brain/packages/orchestrator/src/cortex_orchestrator/memory_builders.py` passes store, embedder,
  clock, scope, policy and audit and no factory. The store mints nothing either: `memories.id` is
  `text PRIMARY KEY` in `docker/postgres/init.sql` with no default, so every id the trail renders
  is 36 characters and the arithmetic holds as written.
- 2026-09-15: closed as both halves rather than the cheap one. The arithmetic reproduces this entry
  exactly: twenty 36-character ids and their JSON come to 1,101 characters, no float renders in
  more than 24, the field cannot pass 1,581, and 467 characters of slack buy 23 characters of id,
  so the worst case crosses `VALUE_CHARS` at 60. Live cosines render at about 18 characters rather
  than 24 and move the crossing to 66, which is why 60 is the number to design against. Both halves
  of the trigger are still unfired. The number is written beside the factory, in the
  `MemoryRecaller` entry of `docs/modules/brain-core.md`, with a pointer to it from the `dropped`
  entry of `docs/modules/brain-memory.md`. The bound at the port is declined there in one sentence:
  the id is the store's identity and a logging bound has no business setting it. What this entry
  did not ask for and got anyway is a test.
  `brain/packages/orchestrator/tests/test_widest_line.py` builds the trail's widest line from ids
  minted by a `MemoryRecaller` constructed the way the composition root constructs it, scores every
  candidate at the widest rendering a Python float has, and asserts the `dropped` field is not cut.
  A factory minting 60 characters fails it, and fails nothing else in the tree. Recorded in
  ADR-0051 decision 15.
