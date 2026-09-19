# Brain-generated summary titles

**Status:** done 2026-07-16
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

Titles were derived from the first user message (`summarize_session`). A brain-generated summary
title now replaces that, and the overlay's own live `deriveTitle` stays for a chat that is not yet
stored.

The entry said this sat behind an unchanged `SessionSummary`, which hid four real costs: a new
`SessionStore.set_title` write method, a store-layout change (a `cortex:session:{id}:title` string
key), a list-read change (`summarize_ends` takes a `title_override`, batched into the same pipeline
as each chat's two ends), and a decision about which model tier generates it and when.

The resident cortex generates it on a session's first turn only, from the opening exchange, and it
is stored before `TurnCompleted`. That makes it race-free: the reply's `stream` has released its GPU
lease, so the title call acquires it sequentially, and no port widening is needed because the engine
already calls the async `InferenceBackend`. Because the title is stored before completion, the
overlay's turn-completion refresh already sees the final title. A blank or absent title falls back
to the first-message derivation, and every title is re-bounded to `TITLE_MAX` at read time.

It ships off by default (`CORTEX_GENERATE_TITLES`), because it costs one inference call per new
session. Found live against a real reasoning cortex (Qwen 2B): a reasoning model may emit only
`reasoning_content` and no reply (one case: 13,882 reasoning characters, zero content), so the
generated title is empty and the first-message title stands.

That half closed on 2026-08-06, once `InferenceBackend.stream` could take per-request bounds.
`generate_title` sends `TITLE_BOUNDS` (`max_tokens=32, thinking=False`, 32 being `TITLE_MAX` in the
request's own unit, so hitting the cap falls past the 48 characters `clean_title` keeps). Measured
on the shipped cortex over one prompt, three runs each way: 235 to 303 decoded tokens at 7.9 s to
10.4 s became 4 tokens at 0.2 s to 0.3 s, for the same titles.

## History

- 2026-07-16: Closed, and it opened the open-chat header-consistency entry behind it. It is another
  entry that understated its cost: the value type held, but the real build added a write method, a
  store-layout change, a list-read change, and a decision about tier and timing.
- 2026-07-16: The audit of the session-history summarization and model-based reranker pair found the
  non-reentrant GPU-lease hazard avoidable here, because selection completes before the reply stream
  acquires the lock. Proven against the real manager: a drained acquire followed by the reply's
  acquire succeeds, while a held-open call deadlocks.
- 2026-08-06: The empty-reply half closed when per-request bounds shipped as `GenerationBounds` on
  `InferenceBackend.stream`. Capping tokens while leaving thinking on is a certain failure for this
  call, empty three times in three at each of 16, 32 and 64 tokens, because the answer is a few
  tokens and the deliberation before it is hundreds. The session title was one of three passes that
  discarded their own deliberation and took the new bounds, beside the history recap's fold and the
  recall rank.
