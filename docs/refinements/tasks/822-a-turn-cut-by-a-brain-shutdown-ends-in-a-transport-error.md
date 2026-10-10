# A turn cut by a brain shutdown ends in a transport error

**Status:** open, actionable
**Area:** rpc-transport
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 1
**Verified:** 2026-10-10

On the Linux shell on 2026-10-10
([readings](../../readings/store-and-process-restarts.md#the-brain)) the brain's container was
restarted 7 s into a 300-word essay. `serve` in
[server.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/server.py) answers the
SIGTERM with `server.stop(grace=_SHUTDOWN_GRACE_SECONDS)`, 5 s, yet the model host logged
`cancel task` 3 s after the signal, inside that grace; which side cut the `Converse` call first is
not recorded. The overlay kept the text that had arrived and showed
`Unknown: h2 protocol error: error reading a body from connection` under it, and the store held the
question with no reply. The old brain logged nothing about the cut turn.

[R-814](814-a-reply-that-ends-early-names-the-transport-not-the-cause.md) covers the overlay's
wording for a stream that ends early, and ADR-0011 decision 1 that a cancelled turn stores the
question alone. Neither covers what the brain can do in its grace period: it knows it is stopping,
but every in-flight turn ends the way a `docker kill` ends it.

## Proposal

- At the start of the grace period, end every in-flight turn with a typed error event, for example
  `brain_stopping`, sent before the stream closes, and log the session and turn ids. The overlay
  then shows the brain's own sentence instead of the transport's, without R-814's pick.
- Whether the text already sent is stored as a cut reply is the same choice
  [R-816](816-a-stopped-reply-goes-on-writing-and-is-not-kept.md) holds for a Stop, and is left to
  it.

**Reproduction.** Send a request for a long essay and `docker restart` the brain's container while
the reply streams; read the overlay and the chat's message list.

## History

- 2026-10-10: filed from the brain restart flow on the Linux shell.
