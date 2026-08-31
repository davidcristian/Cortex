# Grammar-constrained subagent output

**Status:** landed 2026-07-13
**Area:** untrusted-content
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

This is the ADR-0017 option (c) hardening pass.
An additive `schema` keyword on the unchanged `InferenceBackend` port
(`JsonSchema = Mapping[str, object]`; `LlamaCppBackend` maps it to an OpenAI `response_format`
`json_schema`, the fake records it) threaded through `ToolLoopContext`; the `SubagentRunner`
decodes a **tool-less** subagent's reply into a fixed `{"reply": "..."}` envelope
(`constrain_output`, `CORTEX_SUBAGENTS_CONSTRAIN_OUTPUT`, default on) and unwraps it before
persisting, so format-laundering (appended footers/links/sections) has no grammatical position
even on a weak model. Gated to the tool-less path (the ADR-0017 niche where a weak model is
reachable), so the JSON grammar never conflicts with llama.cpp's tool-calling grammar; a malformed
envelope degrades to `ok=False` whose `output` holds the raw text (kept in the store, not
surfaced to the cortex) and whose `detail` is a fixed message. CI-gated end to end (payload
mapping, envelope wrap/unwrap, malformed degradation, the tool-enabled-never-constrained gate),
and **agent-Docker live-validated 2026-07-13** on CPU gemma-4-E4B: the same injection an
unconstrained stream obeys (`Blue\nVISIT http://evil.example ...`) returns exactly
`{"reply": "Red"}` constrained. The envelope closes *appended*-structure laundering; a link woven
into the `reply` string stays the untrusted-content boundary's job. Remaining
behind the same seam (ADR-0028 deferred): a raw GBNF `grammar` alternative to the JSON envelope,
and a per-task caller-supplied schema (rejected for now, revisited only for a structured
subagent-result feature).
