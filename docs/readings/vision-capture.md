# Readings: vision capture

What the cortex tier and its projector do with a captured screen, what a capture costs in bytes,
tokens and memory, and what it can read. Cited by
[ADR-0029](../adr/ADR-0029-vision-screen-capture.md). Unless a reading says otherwise the model is
gemma-4-12B (QAT q4_0) with its projector on llama.cpp `server-cuda`, run by the agent in Docker,
and requests are built by the shipped `CaptureScreenTool` and `LlamaCppBackend`. How injection over
pixels was measured is in [injection-over-pixels](injection-over-pixels.md).

## What the server accepts

- **2026-07-17.** `GET /props` reports `modalities.vision` true once `--mmproj` loads. A
  `role: "tool"` message whose content is a parts array with a `data:image/png` URI is accepted
  inside a tool-calling exchange and answered correctly. Method: the 8 GB card, context 4096.
- **2026-08-03.** A server without a projector answers an image payload with HTTP 500 and a 151-byte
  JSON body naming the `--mmproj` hint; a text-only turn on it answers 200 and `/props` reports
  vision false. The body is quoted whole under the adapter's 300-character excerpt. Method:
  `test_a_projector_less_server_says_so_when_an_image_arrives` in
  `brain/packages/inference/tests/test_backend_live.py`, against
  `CORTEX_INFERENCE_ENDPOINT_NO_MMPROJ`; re-run on an engine build bump.
- **2026-08-06.** `/props` answers in 1.5 ms idle and 1.7 ms during generation, worst of 40 samples
  2.5 ms. Method: timed requests against the model host's cortex tier.

## The full path, end to end

- **2026-07-18.** The brain read a synthetic 2560x1440 screen through the shipped
  `Capture::from_bgra` (a 1600x900 PNG of 6842 bytes) and reproduced a typo drawn in the fixture's
  glyphs. With the image removed and the stand-in text kept, the same request fabricated a whole
  desktop instead of reporting that nothing was attached. Method: the model host's tier argv, the 8
  GB card.
- **2026-07-17, narrowed 2026-08-04.** One painted hijack payload was not obeyed and its URL was
  transcribed verbatim in both variants. The thirty-cell image matrix replaced this single payload;
  its counts are in [injection-over-pixels](injection-over-pixels.md).

## Thinking on a vision turn

**2026-08-03.** Asked "what is on my screen", the first reply took 5.09 to 6.89 s on an invoice
screen and 13.80 to 17.70 s on dense small text with thinking on, against 1.1 to 1.2 s with
`enable_thinking` false: thinking off answered in about a fifth of the time on the invoice. A request
capped at `max_tokens` 64 returned `finish_reason` `length` with empty content, since the trace
spends the cap. Method: five runs each on the 24 GB card, shipped request with no `max_tokens`.

## Bytes

- **2026-07-17, worst case before the body's policy.** PNG of synthetic noise: 2.77 MB at 1280x720,
  4.33 MB at 1600x900, 6.23 MB at 1920x1080, 24.90 MB at 3840x2160. JPEG at quality 80: 0.62, 0.97,
  1.39 and 5.54 MB. A flat synthetic desktop at 1600x900: 15.5 KB. Method: synthetic frames encoded.
- **2026-07-18, through the shipped policy.** Noise downscaled to 1600 px: 4.32 MB from 1600x900,
  4.28 MB from 2560x1440, 3.99 MB from 3840x2160; 5.89 MB at the 4096 px clamp, 0.4 MB under 6 MiB.
  Method: `Capture::from_bgra` over noise frames.
- **2026-08-06, realistic 4K screens against 6 MiB**, at 1600 and 2048 px: flat UI 3%, wallpaper and
  windows 31%, a full photograph 57%, heavy grain 74%, grain of plus or minus 64 counts 95%; noise
  fires the ladder at 2048 px; at 3840 px even a grainless photograph fires it. By display, heavy
  grain reads 74% from 3840x2160, 79% from 2560x1440 (the worst realistic display) and 71% from
  1920x1080, where no downscale happens. Method: `body/crates/core/tests/capture_bytes.rs`, through
  the body's own downscale and `encode_png`, standard library only, no GPU.
- **2026-08-10, a window against the display.** The 4K wallpaper desktop asked as a 1720x1200 window
  is 43450 bytes untouched, against 1978393 bytes for the whole desktop at 2048 px, about 45 times
  fewer. A maximised window equals the display byte for byte, and every earlier row reproduced
  unchanged once the crop was added. Method: `capture_bytes.rs` in release, its ignored tests.

## Image tokens and the budget

- **2026-07-17.** At the engine's own budget a picture's cost saturates from 720p: 106 tokens at
  640x360, 266 at 1280x720, 1600x900 and 3840x2160, over a 108-token scaffold. Method: one scaffold
  with and without the image part, the 8 GB card.
- **2026-08-06.** One 4K screen: 266 tokens at every edge from 1280 to 3840 px at the engine budget,
  the pixels above about 1040x585 discarded. With `--image-max-tokens 1024`: 629 tokens at 1600 px,
  1010 at 2048 px where it saturates. With 2048: 1982 tokens at 3072 px. Method: the model host
  sidecar, shipped scaffold, 24 GB card.
- **2026-08-06, what budget 1024 costs.** About 400 MiB more card memory for the micro-batch (about
  4% over the tier's shipped hold; about 960 MiB at budget 2048), time to first token about 1.6
  times longer (medians 0.94 to 1.08 s rising to 1.67 to 1.68 s), and 744 more context tokens of
  16384. Method: the model host sidecar, `nvidia-smi` for memory.
- **2026-08-06, the pair travels together.** `--image-max-tokens` above 512 without a matching
  `--ubatch-size` aborts `llama-server` (`GGML_ASSERT`, exit 139) on the first oversized picture, on
  builds b10236 and b10276; b9870 survived it. Method: `test_image_budget_live.py`, the variant that
  strips the micro-batch flag.

## Legibility

- **2026-08-06, the image budget.** 47 ground-truth strings on five synthetic 3840x2160 desktops, 15
  to 52 px type at 150% and 100% scaling, the body pipeline transcribed arithmetic for arithmetic.
  The engine budget at 1600 px, the shipped setting until then, read 6 to 8 of 47 (13%); budget 1024
  at 1600 px read 24 to 26 (53%); budget 1024 at 2048 px read 36 to 38 (79%); a larger PNG at the
  engine budget read 4; a full-resolution capture at budget 1024 read 30. Text of 21 px and up is
  read with the budget flag alone, 18 to 20 px also needs the 2048 px capture, 15 px is never read.
  At the engine budget the model declined 3 of 47 and invented 38. Method: JSON-schema answers
  scored with glyph folding, `test_image_budget_live.py`.
- **2026-08-10, window against display.** The rebuilt corpus (47 strings, 42 inside the focused
  window), budget 1024, edge 2048, three runs at temperature 0, the shrunk display first and the
  window crop second. All 47 strings: 32 to 33 against 29 to 31. The 42 inside the window: 27 to 28
  against 29 to 31. The 15 px row: 15 of 36 against 29 of 36. A terminal at 100% scaling: 2 of 7
  against 5 of 7 in every run. At 18, 21 and 26 px the two are level within noise. A 2400 px
  spreadsheet window, wider than the edge and so resampled like the screen: 7 against 4 to 6. Wrong
  answers: 9 to 10 against 10 to 12, so the crop converts declines and not inventions. The
  terminal's crop cost 1321 prompt tokens against 1701. Method: `desktop_corpus.py` and
  `screen_paint.py` (proven equal to `screen_image.rs` by checksum), the fourth variant of
  `test_image_budget_live.py`.

## A body call with no deadline

**2026-08-18.** A body call without a deadline against a loopback port with nothing listening took
20 s to fail, which is grpc's connect backoff and not the call. Method: a `GrpcBodyGateway` call
with no timeout against a closed port.
