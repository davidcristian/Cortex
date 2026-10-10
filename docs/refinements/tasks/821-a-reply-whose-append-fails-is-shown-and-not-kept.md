# A reply whose append fails is shown and not kept

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0001](../../adr/ADR-0001-architecture.md)
**Verified:** 2026-10-10

`TurnEngine.handle_turn`
([engine.py](../../../brain/packages/core/src/cortex_core/engine.py)) streams the reply to the
body as it is generated and appends it to the store once, after the last token. When that append
raises `SessionStoreError`, the stream ends in `session_store_unavailable` after the person has
already read the whole reply, and the store keeps the question with no answer. The redis-py client
retries a failed connection with a backoff (its defaults, ten tries) before the error reaches the
adapter. A `docker restart` of Redis in the middle of a reply overlapped no store call of the turn
and lost nothing; Redis stopped for 22 s across a reply's end failed its append. Whether the
client's retries cover a restart that overlaps the append itself was not measured.

On the Linux shell on 2026-10-10
([readings](../../readings/store-and-process-restarts.md#redis)) the overlay drew `Apple and
banana.` and a red bubble under it. The chat then held the question alone, so it shows unanswered
when opened again, and the next turn's model input lacks that answer, although the person saw it.

**Reproduction.** Send a short question and `docker stop` the Redis container within a second;
start it again after the overlay shows the error, then read the chat's message list.

**What deciding it needs.** Whether the final append waits out a store outage for a bounded time
before the turn fails, what that bound is against the body's turn gaps
(`CORTEX_BRAIN_TURN_IDLE_GAP_MS`), and whether the overlay marks a reply that was shown and not
stored. The user message is appended before inference, so the same outage at the start of a turn
fails before anything is shown, which needs no change.

## History

- 2026-10-10: filed from the store and process restart flows run on the Linux shell.
