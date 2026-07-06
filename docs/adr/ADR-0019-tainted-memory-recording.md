# ADR-0019: Recording tainted turns to memory with an untrusted-provenance marker

- **Status:** Accepted (ADR-0013 tainted-memory deferral, landed 2026-07-06)
- **Date:** 2026-07-06

## Context

ADR-0013 drew the poisoning defense bluntly: a turn that reads untrusted content records
**nothing** to memory (`engine.handle_turn`: `if memory and not taint.tainted: record(...)`).
Every stored memory then comes from an untainted turn, so recall is safe to treat as trusted. It is
correct, but it throws away legitimate context. "Summarize the Q3 report email" → the assistant's
answer is useful to remember ("I told the user revenue was flat"), yet the whole exchange is
dropped because the turn touched an untrusted source.

The ROADMAP deferral (ADR-0013, "Context-preserving tainted-memory recording") named the fix:
record the tainted exchange **with a provenance marker**, and **frame it as untrusted on recall**,
preserving the context without reopening the poisoning channel. The recorded text is already the
`User: …\nAssistant: …` exchange. The raw untrusted tool payload was only ever in the in-turn
`Role.TOOL` messages, which are never persisted. What `tainted` records is that the assistant text
was *derived from* untrusted content and so may carry a quote, summary, or latent injection that
must not silently re-enter a future turn as trusted context.

The invariant this generalizes: **untrusted-derived content is fenced-and-tainting wherever the
model sees it.** ADR-0013 held that within one turn (a live tool result). This ADR extends it
across turns (a recalled memory).

## Decision

1. **`MemoryRecord.tainted: bool` is a provenance marker (`memory.py`), default `False`.** It rides
   the `MemoryStore` port exactly as `scope` did (ADR-0008 scoping addendum): the pgvector adapter
   gains a `tainted boolean NOT NULL DEFAULT false` column in the `INSERT`/`SELECT`/row mapping;
   `InMemoryMemoryStore` carries it in the stored record for free. `MemoryRecaller.record(text, *,
   session_id, tainted=False)` threads it; every other field and behavior is unchanged.

2. **Recording is opt-in, one knob: `CORTEX_MEMORY_ON_TAINTED = skip | record` (default `skip`).**
   Mirrors `CORTEX_TOOLS_ON_UNAVAILABLE`. The core takes the bool `TurnCapabilities.
   record_tainted_memory`. The composition root maps the string (the core never reads it).
   `skip` (default) is byte-for-byte the ADR-0013 behavior: a tainted turn records nothing.
   `record` records the exchange with `tainted=True`. An **untainted** turn records normally under
   either value. `skip` is the safe, strictly-additive default, because recording untrusted-derived
   content is a surface a deployment opts into, not the fail-closed baseline.

3. **Recall ALWAYS fences a tainted memory, keying on the record, not the knob (`engine.py`).** A
   recalled `tainted=True` record is wrapped by `wrap_untrusted` with the turn nonce, marks the
   turn tainted (`TaintLedger.ingest_untrusted`), and contributes its URLs to the output
   guardrail's live set (ADR-0015). Trusted memories render plainly as in Slice 5. The
   `SECURITY_PREAMBLE` is injected whenever tools are enabled **or** a tainted memory was recalled,
   so the fence markers are always explained. Keying on the record means a store that accumulated
   tainted memories while `record` was on stays safe after a deployment toggles back to `skip`: the
   knob governs only what is *written*, never how an existing tainted memory is *read*.

4. **Taint propagates through memory (deterministic, not a model judgment).** Recalling a tainted
   memory re-taints the current turn: its gated tools are blocked (ADR-0013) and, under `record`,
   the new exchange is itself recorded `tainted=True`. So untrusted provenance is sticky across
   recall, closing the cross-turn laundering/persistence path that unfenced recording would open.

5. **One fence identity per turn.** The engine builds the `ToolLoopContext` (which carries the
   per-turn `nonce` and `TaintLedger`) **before** assembling the turn's messages, so recall-time
   fencing uses the same nonce the preamble advertises and the tool loop wraps live results with.
   Recall may now taint a turn *before* the loop runs; the output guardrail is opened over the
   ledger's live set after assembly, so a URL a recalled tainted memory carries is already present
   to redact if the reply echoes it.

## Consequences

- Legitimate context from tainted turns is preserved (opt-in) with no poisoning channel: the
  derived memory can only re-enter a future turn as fenced, tainting data, never as trusted
  context. The deterministic untrusted-content stack now spans turns: gate (actions) +
  taint→provenance-marked-memory (poisoning) + **fenced-and-tainting recall (cross-turn)** +
  subagent exclusion (capability) + redaction (content).
- `TaintLedger.ingest_untrusted(content)` is the non-tool-source taint entry (mark + collect
  URLs); `observe(result)` and `mark(trust)` are unchanged, and `observe` still delegates through
  `mark`. The recall path and the tool-loop path now taint by the same mechanism.
- A bare `TurnCapabilities()` and any untainted turn behave exactly as before; the change is
  invisible until a turn both reads untrusted content **and** the knob is `record`, or a tainted
  memory already in the store is recalled.

## Risks

- **Taint spreads on tangential recall.** A semantically-matched but irrelevant tainted memory
  taints an otherwise-clean turn, blocking its gated actions. Fail-closed by design, as the recalled
  content is in the model's context and we do not trust framing to contain it. A *fence-without-
  block* recall mode (relax the gated block, keep the fence) is deferred behind the same seam if
  this proves too blunt.
- **Provenance is binary.** Only the trusted/untrusted bit is recorded; structured provenance
  (source URI, sender) rides the ADR-0013 provenance deferral, joined here once the confirmation UI
  needs to show a source.
- **Two behaviors to cover.** `skip` and `record` both need tests; both are CI-gated over the fakes
  (the `InMemoryMemoryStore` carries `tainted` in the record), and the pgvector column is
  host-validated by the live memory contract check.

## Deferred (behind the unchanged `MemoryStore` / `MemoryScope` / `MemoryRecaller` / `TaintLedger` seams)

- **Structured provenance beyond the bit** (source URI, sender) joins the ADR-0013 provenance
  deferral; the confirmation UI is the first consumer.
- **Fence-without-block recall** fences a recalled tainted memory but does not block
  the turn's gated tools, if taint-spread on tangential recall proves too blunt.
- **Summarizing a tainted exchange before recording** is a lossy model pass to store only the safe
  gist; memory-summarization territory (ADR-0008/0014), distinct from this binary marker.
- **Per-scope / per-age eviction of tainted memories** is the memory-retention deferral (ADR-0008),
  which a tainted-provenance filter would compose with cleanly.
