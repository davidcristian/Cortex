# Two agent-Docker validations

**Status:** landed 2026-08-03
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Written down 2026-07-19, having lived only in
[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)'s Consequences with nothing tracking them,
so the work was owed with nothing to bring it back. That ADR named four measurements as still to run
when it was accepted. Two of them ran and are recorded in its 2026-07-18 agent-validation section
(the whole path through the real `LlamaCppBackend` rather than raw HTTP, and an injection arm on the
shipped payload). Two did not: **whether thinking needs disabling on a vision turn** under the
shipped parts payload, and **`llama-server`'s `mmproj`-less error body text**, which that ADR also
carries on its assumptions list precisely because the bounded 300-character non-2xx excerpt was
built to surface it, so the excerpt's whole value rests on a string nobody has read. Both are
**agent-side, not host-side**, which is why they belong in this backlog rather than on a user list:
the same 8 GB dev GPU that ran the 2026-07-18 validation holds the cortex beside its projector, so
nothing about them needs the host hardware. The disable-thinking lever itself is a separate open
entry ([inference-model-manager.md](../index.md#inference-model-manager)); what is unmeasured here
is only whether a vision turn is the case that needs it.

**Both ran 2026-08-03 and the entry closes**
([ADR-0029 agent-validation addendum](../../adr/ADR-0029-vision-screen-capture.md)). The cortex came
up the shipped way, the model-host sidecar under the gpu override with
`CORTEX_MMPROJ_FILE_CORTEX` naming the projector beside the weights, and its `/props` answered
`modalities: {'vision': True, ...}` again, this time on the 24 GB card rather than the 8 GB one
the entry expected; neither check needs either card in particular. Every payload was built by the
shipped code (`CaptureScreenTool` over an in-memory body, `result_message`'s fence,
`security_preamble_message`, `call_message`, and `LlamaCppBackend` doing the serialisation), so
what was measured is the request the brain really sends.

**Thinking does not need disabling on a vision turn, and the question was pointed at the wrong
risk.** The feared failure is a reply that never arrives because the budget went to
`reasoning_content`, and the shipped path cannot reach it: the request carries no `max_tokens` at
all (`_build_payload` emits `model`, `messages`, `stream`, plus `tools` and `response_format` when
present) and the shipped server reports `n_predict: -1`. Ten image runs over two screens returned a
reasoning trace and a non-empty reply every time. The failure is real where a cap exists, which is
why the absence of one matters rather than being luck: the identical payload with `max_tokens: 64`
comes back `finish_reason: "length"` with 247 characters of reasoning and an empty `content`, while
200, 400 and uncapped all answer normally. Two CI-gated tests in
`packages/inference/tests/test_backend.py` pin the exact request body, and planting a `max_tokens`
in `_build_payload` makes both fail, so the property is held by the suite rather than by this note.
What thinking really costs a vision turn is time. On the invoice screen the reply began 5.09 to 6.89
s in (median 6.14) and ran 9.5 to 11.7 s total; on a screen packed with small text it began 13.80 to
17.70 s in (median 15.29) and ran 28.4 to 32.8 s. The same payload with `chat_template_kwargs:
{"enable_thinking": false}` began in 1.1 to 1.2 s, spent 93 completion tokens against 283, and read
the same numbers off the screen. The control arm is what makes this a vision finding rather than a
model finding: with the `ImagePart` removed and the stand-in text kept, the model thought on only 2
of 5 runs and its first word came at a median 0.41 s, so a picture makes a think near-certain, while
the length of a think is not a property of pixels (the two pixel-less thinks, 858 and 1408
characters, are longer than every invoice-screen one). Both figures are for the open-ended ask,
"what is on my screen?"; a narrow one ("what is the total due shown on my screen?") skipped the
think on some image runs and answered in 1.8 s, so this is a tendency of the open question rather
than a rule about pixels. That is data for the disable-thinking lever, which stays open where it is
([inference-model-manager.md](../index.md#inference-model-manager)) and now has a latency number
rather than an emptiness risk behind it.

**The `mmproj`-less error body says exactly what this ADR assumed it would**, so the assumption
is now a measurement and the excerpt's whole value is confirmed rather than hoped for. A server on
the same weights started without the `--mmproj` pair answers an image-bearing shipped payload with
HTTP 500, `content-type: application/json`, and this body verbatim, 151 bytes, identical whether
the request streams or not:
`{"error":{"code":500,"message":"image input is not supported - hint: if this is unexpected, you
may need to provide the mmproj","type":"server_error"}}`. llama.cpp writes the word "hint" itself.
151 bytes sits well inside the 300-character bound, so the excerpt quotes the whole body and the
raised `InferenceError` reads `llama-server answered 500 for model 'cortex': {...}` at 197
characters, which `converse_stream` then hands to the seam as `ERROR_CODE_INFERENCE_FAILED` with
`str(err)`. Nothing about the excerpt needs changing. Two things bound how anyone meets that 500:
the same projector-less server reports `modalities: {'vision': False, ...}`, so the startup probe
refuses to advertise `capture_screen` at all, which leaves a mid-session restart without the pair
(the live-probe-refresh entry above) and a forced `CORTEX_VISION=on` as the ways in. The string is
a llama.cpp build's, not a contract, so it landed as a re-runnable canary rather than as a note:
`test_a_projector_less_server_says_so_when_an_image_arrives` in
`packages/inference/tests/test_backend_live.py` is integration-marked, points at
`CORTEX_INFERENCE_ENDPOINT_NO_MMPROJ`, and asserts the status prefix, that the quoted body still
parses as whole JSON, and that the hint names the `mmproj`. It was proved able to fail before
being trusted: against the projector-loaded server it fails with `DID NOT RAISE`.

**One correction came out of proving that**, and it is the reason the canary carries a full
conversation. A bare user-plus-tool pair is a malformed exchange, and the projector-loaded server
answers it `400 {"error":{"code":400,"message":"Failed to tokenize prompt", ...}}`, which reads
like an image problem and is not one. Under the shipped scaffold, the assistant's own tool call
included, square images from 1x1 to 1280x1280 all answer 200, and the picture's prompt-token cost
rises 51, 171, 258 and saturates by 896 px, consistent with the 266-token saturation this slice
measured before deciding. So there is no minimum image size, nothing new is deferred, and the
measurements above were all taken with the assistant message in place.

## Trail

- 2026-07-19: written down, taking the area 18 to 19. This is work that had lived only in ADR-0029's
  Consequences with nothing tracking it, so it was owed with nothing to bring it back. The same pass
  settled a naming question the area had been carrying silently, stating both the split of region
  capture from legibility at 4K and the deliberate exclusion of the accepted residual.
- 2026-08-03: both ran and the entry closed whole, moving the area's count 17 to 16. Neither half
  needed a code change, and both are the kind of claim a llama.cpp build can invalidate, so the
  error string landed as an integration-marked canary proved able to fail before being trusted.
