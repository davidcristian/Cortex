# A read timeout on the subagent HTTP client

**Status:** done 2026-08-09
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

`build_subagents` built `httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None)`, so one wedged
`llama-server` stream held its admission forever and every queued peer waited behind it. `read=None`
was deliberate, since a generation may legitimately stream for minutes on CPU, so the fix is a
generous per-stream ceiling rather than a short one, and it belongs to the inference adapter.

There were two unbounded clients rather than one, and the second matters more: the resident tier's
(`builders.build_inference_backend`) had the same `read=None`, and after a handoff the deep model
streams through that same object, so the site the entry missed serves the slowest model in the
lineup. Both are now built by `builders.build_generation_client`. The entry could miss it because
`builders.py` documented the policy as shared while naming only the connect phase.

The ceiling is two numbers rather than one: `CORTEX_INFERENCE_STALL_TIMEOUT_S` at 120 s and
`CORTEX_SUBAGENTS_STALL_TIMEOUT_S` at 600 s, because the worst legitimate silence differs by an order
of magnitude between the tiers, and one number would have to be the loose one, parking a wedged
cortex turn for the CPU pool's whole allowance. Both are derived from measurements: 17.5 s of
contended time to first token scaled by the deep tier's own cost for the first, and twice the 300 s
upper end of a measured whole CPU subtask for the second.

The semantics matter: httpx applies a read timeout to one socket read, so this bounds the gap between
chunks and never a generation's length, and backpressure from the body does not trip it. The pool's
wire queue is also shorter than its admission queue, since a backend holds its lease for the whole stream, so
spawns of one roster entry on one target run one after another on the brain side, ahead of the
request.

## History

- 2026-07-16: Opened by the hard budget limit's close, as one of the two waits nothing bounded.
- 2026-08-09: Closed on two clients rather than the one it named, recorded at
  [ADR-0005 decision 7](../../adr/ADR-0005-llamacpp-engine.md).
- 2026-08-09: The same pass opened the failure a stall detector cannot see, a subagent that keeps
  talking, and this close is what let the bounded admission wait close hours later.
