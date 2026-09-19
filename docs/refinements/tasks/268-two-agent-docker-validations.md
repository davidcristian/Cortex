# Two agent-Docker validations

**Status:** done 2026-08-03
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) named four measurements as still to run
when it was accepted. Two ran and are recorded in its 2026-07-18 agent-validation section. Two did
not: whether thinking needs disabling on a vision turn under the shipped parts payload, and what
`llama-server`'s error body says when it has no `mmproj`, which matters because the bounded
300-character non-2xx excerpt was built to show exactly that string and nobody had read it. Both
are the agent's to run rather than the host's, since the dev GPU holds the cortex beside its
projector. The setting that disables thinking is a separate entry
([inference-model-manager.md](../index.md#inference-model-manager)); what was unmeasured here is
only whether a vision turn is the case that needs it.

Both ran 2026-08-03 ([vision-capture](../../readings/vision-capture.md)). The cortex came up the
shipped way, the model-host sidecar under the gpu override with `CORTEX_MMPROJ_FILE_CORTEX` naming
the projector beside the weights, and its `/props` answered `modalities: {'vision': True, ...}`,
this time on the 24 GB card. Every payload was built by the shipped code (`CaptureScreenTool` over
an in-memory body, `result_message`'s fence, `security_preamble_message`, `call_message`, and
`LlamaCppBackend` doing the serialisation), so what was measured is the request the brain really
sends.

Thinking does not need disabling on a vision turn, and the question was pointed at the wrong risk.
The feared failure is a reply that never arrives because the budget went to `reasoning_content`,
and the shipped path cannot reach it: the request sends no `max_tokens` at all (`_build_payload`
emits `model`, `messages`, `stream`, plus `tools` and `response_format` when present) and the
shipped server reports `n_predict: -1`. Ten image runs over two screens returned a reasoning trace
and a non-empty reply every time. The failure is real where a cap exists, which is why the absence
of one matters: the identical payload with `max_tokens: 64` comes back `finish_reason: "length"`
with 247 characters of reasoning and an empty `content`, while 200, 400 and uncapped all answer
normally. Two tests in `packages/inference/tests/test_backend.py` assert the exact request body,
and planting a `max_tokens` in `_build_payload` makes both fail.

What thinking costs a vision turn is time. On the invoice screen the reply began 5.09 to 6.89 s in
(median 6.14) and ran 9.5 to 11.7 s in total; on a screen packed with small text it began 13.80 to
17.70 s in (median 15.29) and ran 28.4 to 32.8 s. The same payload with `chat_template_kwargs:
{"enable_thinking": false}` began in 1.1 to 1.2 s, spent 93 completion tokens against 283, and read
the same numbers off the screen. The control makes this a vision finding rather than a model
finding: with the `ImagePart` removed and the placeholder text kept, the model thought on only 2 of
5 runs and its first word came at a median 0.41 s, so a picture makes a think near-certain, while
the length of a think is not a property of pixels (the two pixel-less thinks, 858 and 1408
characters, are longer than every invoice-screen one). Both figures are for the open-ended question
"what is on my screen?"; a narrow one ("what is the total due shown on my screen?") skipped the
think on some image runs and answered in 1.8 s.

The `mmproj`-less error body says exactly what the ADR assumed. A server on the same weights
started without the `--mmproj` pair answers an image-bearing shipped payload with HTTP 500,
`content-type: application/json`, and this body word for word, 151 bytes, identical whether the
request streams or not:
`{"error":{"code":500,"message":"image input is not supported - hint: if this is unexpected, you
may need to provide the mmproj","type":"server_error"}}`. llama.cpp writes the word "hint" itself.
151 bytes is well inside the 300-character bound, so the excerpt quotes the whole body and the
raised `InferenceError` reads `llama-server answered 500 for model 'cortex': {...}` at 197
characters, which `converse_stream` passes on as `ERROR_CODE_INFERENCE_FAILED` with `str(err)`.
Nothing about the excerpt needs changing. Two things bound how anyone meets that 500: the same
projector-less server reports `modalities: {'vision': False, ...}`, so the startup probe does not
advertise `capture_screen` at all, which leaves a mid-session restart without the pair and a forced
`CORTEX_VISION=on` as the ways in. The string belongs to a llama.cpp build rather than to a
contract, so it is committed as a re-runnable check:
`test_a_projector_less_server_says_so_when_an_image_arrives` in
`packages/inference/tests/test_backend_live.py` is integration-marked, points at
`CORTEX_INFERENCE_ENDPOINT_NO_MMPROJ`, and asserts the status prefix, that the quoted body still
parses as whole JSON, and that the hint names the `mmproj`. It was proved able to fail before being
trusted: against the projector-loaded server it fails with `DID NOT RAISE`.

Proving that turned up one correction, which is why the check sends a full conversation. A bare
user-plus-tool pair is a malformed exchange, and the projector-loaded server answers it `400
{"error":{"code":400,"message":"Failed to tokenize prompt", ...}}`, which reads like an image
problem and is not one. Under the shipped scaffold, the assistant's own tool call included, square
images from 1x1 to 1280x1280 all answer 200, and the picture's prompt-token cost rises 51, 171, 258
and stops growing by 896 px, consistent with the 266-token saturation measured before the decision.
So there is no minimum image size, and the measurements above were all taken with the assistant
message in place.

## History

- 2026-07-19: Written down. This work had lived only in ADR-0029's Consequences with nothing
  tracking it, so it was owed with nothing to bring it back.
- 2026-08-03: Both ran and the entry closed. Neither half needed a code change, and both are the
  kind of claim a llama.cpp build can invalidate, so the error string was committed as an
  integration-marked check proved able to fail before being trusted.
