# Fence-without-block recall mode

**Status:** open, waiting for its trigger
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Trigger:** taint-spread on tangential recall proving too blunt. It can only show itself once the
memory store holds a tainted row, and a deployment writes one only under
`CORTEX_MEMORY_ON_TAINTED=record` (the default `skip` drops a tainted turn from memory), so the
cheap reading is `select count(*) filter (where tainted) from memories`, which returned 0 on
2026-09-17.
**Verified:** 2026-09-17

Left behind by [R-072](072-tainted-memory-recording.md): a recall mode that fences a tainted
memory without tainting the turn, if spreading taint on a tangential recall turns out to be too
blunt.

## History

- 2026-09-11: Not fired. The mechanism is unchanged: `_recalled_context` in `turn_context.py`
  fences a recalled tainted memory and taints `context.taint`, so a tangential tainted hit still
  closes the turn's tools that need approval. Whether that has caused a problem was read from the
  store rather than reasoned about: the stack was down, so postgres was started alone from its
  stored volume, and `memories` holds 2 rows, both with `tainted = false`, so no tainted memory
  has ever been recalled on this deployment. Postgres was stopped again afterwards. One design
  since has chosen the mode this entry defers, for a different message: the summarizing window's
  recap is fenced at both ends without spreading taint (ADR-0038 decision 19), because the plain
  history window already hands the model the same text unfenced. That argument does not transfer
  to recall, whose fenced text is nowhere else in the window. A precise fence over recall would
  need the stored per-turn marker [R-082](082-replayed-quoted-injection.md) waits on, so the two
  entries meet at one design.
- 2026-09-17: Not fired, and the trigger now names the setting it depends on. `_recalled_context`
  (`turn_context.py:177`) still hands every hit to `_render_memory_context`, which fences each
  tainted record and calls `taint.ingest_untrusted` on it (`turn_context.py:115-118`), and that
  file has not changed since 2026-08-31. A tainted row reaches the store only when
  `MemoryConfig.on_tainted` is `record` (`config.py:271`, default `skip`), which
  `docker-compose.memory.yml` passes through by name and never sets, so a default deployment
  cannot produce what the trigger waits for. The store was read again, from a throwaway postgres
  on the stored volume with no network, stopped after the query: 2 rows, 0 tainted, the newest
  written 2026-08-11. The fix costs more than a skipped call: `ingest_untrusted` is also what adds
  a recalled memory's URLs to the ledger the output guardrail removes from, and
  `turn_output.py:189` stores a turn to memory as trusted when its ledger is clean, so an exchange
  built on a tainted memory would be stored again without the marker. A mode that fences without
  tainting has to keep those two effects while dropping the tool block.
