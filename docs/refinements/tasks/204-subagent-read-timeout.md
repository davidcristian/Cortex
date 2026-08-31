# A read timeout on the subagent HTTP client

**Status:** landed 2026-08-09
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The entry read: "*Fix when it bites.* The actual unbounded-wait hazard under the admission budget:
`build_subagents` builds `httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None)`, so one wedged
`llama-server` stream holds its admission forever and every queued peer waits behind it. `read=None`
is deliberate (a generation may legitimately stream for minutes on CPU), so the fix is a generous
per-stream ceiling, not a short one, and it belongs to the inference adapter (ADR-0005), not the
scheduler." Every word of that held except the count.
**There were two unbounded clients, not one**, and the second is the one that matters most: the
resident tier's (`builders.build_inference_backend`) carried the same `read=None`, and after a
handoff the deep model streams through that very object, so the site this entry missed serves the
slowest model in the lineup. Both are now built by `builders.build_generation_client`, and the
reason the entry could miss it is that `builders.py` documented the policy as shared ("one knob")
while naming only the connect phase. The ceiling is what the entry asked for, generous and per
stream, and it is **two** numbers rather than one: `CORTEX_INFERENCE_STALL_TIMEOUT_S` 120 s and
`CORTEX_SUBAGENTS_STALL_TIMEOUT_S` 600 s, because the worst legitimate silence differs by an order
of magnitude between the tiers and one number would have to be the loose one, parking a wedged
cortex turn for the CPU pool's whole allowance. The derivations are measurements: 17.5 s of
contended time to first token scaled by the deep tier's own cost for the first, and twice the 300 s
upper end of a measured whole CPU subtask for the second. What the entry could not have known,
because the runbook note postdates it, is that the pool's wire queue is shorter than its admission
queue: a backend holds its lease for the whole stream, so spawns of one entry on one target are
serial **brain side**, ahead of the request, and this ceiling covers one call's own first token
rather than a peer's generation. The semantics matter here: httpx applies a read timeout to one
socket read, so this bounds the **gap between chunks** and never a generation's length, and seam
backpressure does not trip it.

## Trail

- 2026-07-16: Opened by the hard budget wall's close, as one of the two waits nothing bounded, and
  it is the one this area called the actual unbounded-wait hazard.
- 2026-08-09: Landed on two clients rather than the one it named, recorded at the
  [ADR-0005 stall-ceiling addendum](../../adr/ADR-0005-llamacpp-engine.md) and at the
  [ADR-0012 read-timeout addendum](../../adr/ADR-0012-resource-governance.md), as a per-read stall
  ceiling of 120 s on the resident tier and 600 s on the pool that bounds the gap between chunks and
  never a generation's length.
- 2026-08-09: The same pass opened the failure a stall detector cannot see, a subagent that keeps
  talking, and this landing is what let the bounded admission wait close hours later.
