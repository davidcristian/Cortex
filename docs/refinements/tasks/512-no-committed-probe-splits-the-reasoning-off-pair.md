# No committed probe sends the request's own trace budget, or pairs two runs at a seed

**Status:** done 2026-09-11
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)

Two gaps, both in what a committed file can send rather than in what it records.

The request gap: `brain/packages/orchestrator/tests/test_envelope_cost_live.py` runs the shipped
`SubagentRunner`, so it sends exactly what `PlacedAttempt` sends, which names no `trace_tokens`. A
setting substituting a count into the bounds on the way past, the way `_Recording.substitute` already
does for the schema, would make the request-key measurement reproducible by a committed file.

The seed gap is what makes two runs comparable. The envelope harness cannot send a seed without
leaving the shipped path: it runs the real `SubagentRunner`, `PlacedAttempt` builds the request, and
`GenerationBounds` has no seed field, so seeding it is either a port change on a field no deployment
would set, or a request the harness posts itself, which costs the one property that harness exists
for. Without a seed a committed file can report a rate and cannot report that two variants drew the
same completion.

## History

- 2026-08-30: opened by the close of
  [R-500](500-the-garbled-channel-marker-has-no-attributed-cause.md), whose ADR-0049 drew six
  variants by hand off `build_payload` and named the three readings no committed probe takes.
- 2026-09-02: a third hand run, by the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md), which drew 320 variants
  off `build_payload` and the injection harness's corpus from two scratch files. It adds a fourth
  reading: what the reply contains, since a thought the channel no longer shows can arrive inside
  `reply` as a narration or a plan.
- 2026-09-09: claims checked against the code, and the reading gap does not exist. Three of the four
  readings this entry says no committed probe takes are recorded by committed files, and every one
  was already there when the entry was written: `reasoning_head`, `stream_head` and the whole
  `output` in `test_envelope_cost_live.py` since 2026-08-26, and the `/apply-template` rendering in
  `test_thinking_switch_live.py` since 2026-08-28, read back by `just switch-tail`. What survives is
  the request key and the seed, so the body above is rewritten around those two. The trigger is gone
  with the deferral: its first clause fired on 2026-09-02, when the image under this stack had moved
  from `b10666-4e97ac86e` to `b10680-d7bd3bfca` and the rates were recomputed by two scratch files.
- 2026-09-10: checked again, and the seed half is wrong as written. Two committed live probes have
  sent llama.cpp a `seed` since 2026-09-06, `_draw` in
  [test_uid_reading_live.py](../../../brain/packages/orchestrator/tests/test_uid_reading_live.py)
  and the same shape in `test_unfenced_correction_live.py`, and the first runs two variants over the
  same twenty seeds. So what survives is narrower: the envelope harness cannot send one without
  leaving the shipped path.
- 2026-09-11: closed. Both settings are in `test_envelope_cost_live.py`.
  `CORTEX_ENVELOPE_TRACE_TOKENS` is written into the runner's bounds on the way past, with
  `send_trace_budget` on and the engine asked first whether it reads the key, which is a second half this
  entry never named: the harness built its backend with the probe off, so a count in the bounds
  alone would have been dropped by `build_payload`. `CORTEX_ENVELOPE_SEED` is written onto the body
  the shipped adapter built, on the transport, a third option between the two named on 2026-09-10
  and the reason it was chosen: the port gains no field for a measurement and the runner is still
  what runs. Drawn on the default pick over the two bodies the traces fall on: identical on 4 of 4
  cells between two runs at one seed in the same prompt-cache state, 2 of 4 across a cold start, the
  key on top of the flags changing nothing on 4 of 4, and the marker fragments redrawn by seed.
  ADR-0050 publishes the rows; the identity count was made by a scratch script, filed as
  [R-633](633-the-paired-arm-identity-is-counted-by-a-scratch-script.md).
