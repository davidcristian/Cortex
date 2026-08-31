# Brain-generated summary titles

**Status:** landed 2026-07-16
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)

Titles derive from the first user message (`summarize_session`);
a brain-generated summary title would replace that behind the unchanged `SessionSummary`. The
overlay's own live-title `deriveTitle` stays for a not-yet-persisted chat.
**Landed 2026-07-16 ([ADR-0021 titles addendum](../../adr/ADR-0021-session-read-seam.md)), and the
entry undersold the cost.** The wire/port value `SessionSummary` is unchanged, but "behind the
unchanged `SessionSummary`" hid four real costs (this backlog's own warning about this area,
again): a new `SessionStore.set_title` write method, a store-layout change (a
`cortex:session:{id}:title` string key), a list-read change (`summarize_ends` takes a
`title_override`, batched into the same pipeline as each chat's two ends), and a tier/timing
decision. The resident **cortex** generates it on a session's **first turn only**, from the
opening exchange, and it is persisted **before** `TurnCompleted`. That is what makes it
hazard-free and race-free: the reply's `stream` has released its GPU lease, so the title call is
a sequential acquire (never the re-entrant hazard that blocks the reranker), and it needs **no**
async-port widening (the engine already calls the async `InferenceBackend`); and because the
title is stored before completion, the overlay's turn-completion refresh already sees the final
title, so it never rewrites *after* the refresh, which is the race this entry inherited from the
summon-edge refresh above. A blank/absent title falls back to the first-message derivation, and
every title is re-bounded to `TITLE_MAX` at read time. Shipped **off by default**
(`CORTEX_GENERATE_TITLES`): it costs one inference call per new session, and, found live against
a real reasoning cortex (Qwen 2B), a reasoning model may emit only `reasoning_content` and no
reply (one case: 13,882 reasoning chars, zero content), so the generated title is empty and the
first-message title stands. The reasoning-filter and empty-fallback are proven correct by that;
the finding is that reliable *content* wants thinking disabled or a token cap, which
`InferenceBackend.stream` cannot yet express (it reopens as a consumer of the disable-thinking /
token-budget inference deferral, not as new title work). Gated at 100% with four guards
mutation-proven (title override, first-turn-only, empty title rejected, reasoning ignored).
**That half closed 2026-08-06 ([ADR-0021 addendum](../../adr/ADR-0021-session-read-seam.md),
[ADR-0038](../../adr/ADR-0038-ranked-recall.md) bounded-side-calls addendum):** the port learned to
carry per-request bounds for the history fold, and the title pass was the caller this entry had
been waiting for. `generate_title` sends `TITLE_BOUNDS` (`max_tokens=32, thinking=False`, 32
being `TITLE_MAX` in the request's own unit, so a cap-hit lands past the 48 characters
`clean_title` keeps and cannot change a stored title). Measured on the shipped cortex over one
prompt, three runs each way: 235 to 303 decoded tokens at 7.9 s to 10.4 s became **4 tokens at
0.2 s to 0.3 s, for the same titles**. `CORTEX_GENERATE_TITLES` still ships off, on the reason
that survives (an extra inference call per new session, now a cheap one).

## Trail

- 2026-07-16: The titles landed and opened the open-chat header-consistency item behind them.
  The index records this as another entry that undersold its cost: the value type held, but
  the honest build added a `set_title` write method, a store-layout change, a list-read
  change, and a tier/timing policy, generated at turn end so it needs neither the read-path
  GPU-lease hazard nor an async-port widening.
- 2026-07-16: The audit of the session-history summarization and model-based reranker pair the same
  day found the non-reentrant GPU-lease hazard navigable by this generator's sequential-drain
  discipline, the reply's lock not yet being held at selection time, and the index records that
  discipline as proven against the real manager: a drained acquire followed by the reply's acquire
  succeeds, while a held-open call deadlocks. The index states this against the structural nesting
  the memory entry's "inside a turn that already holds the lease" had implied, since selection
  completes before the reply stream acquires the lock.
- 2026-08-06: The generated title's empty-reply half closed when the bounded side calls landed,
  the lever it had been waiting on since 2026-07-16. A title now sends `max_tokens=32,
  thinking=False`, and on the shipped cortex 235 to 303 decoded tokens at 7.9 s to 10.4 s
  became 4 tokens at 0.2 s to 0.3 s for the same titles run for run. The index adds that the
  capped-with-thinking trap that went either way on the history fold is a certainty on this
  call, empty three times in three at each of 16, 32 and 64 tokens, because the answer is a
  few tokens and the deliberation before it is hundreds.
- 2026-08-06: The index adds that this pass and the model-based recall rank were both re-derived
  from the code before the bounding work and that both claims held: each ran `drain_text` with no
  bounds, so each threw away everything the model had deliberated. The lever shipped that day as
  `GenerationBounds` on `InferenceBackend.stream`, and the session title was one of the three passes
  that discard their own deliberation and took it, beside the history recap's fold and the recall
  rank, which narrowed the disable-thinking / token-budget deferral rather than closing it and left
  the user-facing reply, which sends no bounds by design, as the whole of what stays deferred there.
  The same day's ranked-recall design work settled the lease sequencing as a `drain_text` helper
  that leaves the adapter's acquire block in a `finally`, which the title generator now also uses.
