# Region and window capture, and legibility at 4K

**Status:** done 2026-08-10
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

The projector tiles a picture into a bounded token budget (266 tokens for anything from 720p up),
so a 4K desktop downscaled to 1600 px may render small text unreadable. The first fix was a
deployment flag, llama.cpp's `--image-max-tokens`; the real fix is capturing a window rather than a
bigger PNG.

Measured 2026-08-06 ([ADR-0029 decision 17](../../adr/ADR-0029-vision-screen-capture.md)). Five
synthetic 3840x2160 desktops with 47 ground-truth strings from 15 px to 52 px (a code editor, a
terminal, a browser article, a spreadsheet, a chat client; light and dark; 150% and 100% scaling)
were put through a transcription of the body's own `box_filter`, proven equal to the Rust loop, and
read by the shipped cortex. The shipped deployment read 6 to 8 of 47, the flag alone read 24 to 26,
and the flag with `CORTEX_BODY_CAPTURE_MAX_EDGE=2048` read 36 to 38, against a 400 px control at 2.
That is 13% to 79% for about 400 MiB of VRAM, 0.6 s of time to first token, and 744 context tokens
per capture.

Four things the entry did not know. The flag was not reachable, because `ModelHostConfig` builds
the cortex tier's argv and had no way to pass it. The flag alone crashes the server: a picture is
one non-causal chunk and llama.cpp asserts the micro-batch covers it, so a raised budget without
`--ubatch-size` aborts `llama-server` with SIGSEGV on the first oversized picture. Both are now one
setting, `CORTEX_IMAGE_MAX_TOKENS`, which emits the pair. A bigger PNG buys nothing (4 of 47 at a
3072 px capture on the shipped budget), and a full-resolution capture at the raised budget is worse
than a 2048 px one on identical tokens, because the encoder's own resize is a poorer filter than
the body's box average. And the model does not say it cannot read: with the source size in front of
it and "unreadable" offered as an answer, the shipped deployment declined on 3 of 47 and invented
the rest.

`CORTEX_IMAGE_MAX_TOKENS=1024` and `CORTEX_BODY_CAPTURE_MAX_EDGE=2048` became the defaults on
2026-08-06 (ADR-0029 decision 17), both still resettable to `0`. Through the body's own downscaler
and encoder, a 4K frame costs 243 KB as a text desktop, 1.98 MB as a wallpaper under two windows,
3.59 MB as a full-screen photograph and 4.67 MB with heavy grain over it
([`capture_bytes.rs`](../../../body/crates/core/tests/capture_bytes.rs)). How much grain survives
depends on the ratio between the display and the requested edge: a 4K screen averages three and a
half source pixels into every output pixel and most of the grain dies there, while a display nearer
2048 px averages almost nothing. So a 2560x1440 desktop under the same grain costs 5.02 MB, which
is 79% of the 6 MiB ceiling and the worst realistic case, while 1920x1080 is 71% because it is
already inside the requested edge. Nothing a person would look at reaches the halving ladder at the
shipped default. The same correction fixed the test harness, which compared the returned width
against the requested edge and so read an untouched 1920x1080 capture as a halved one; it compares
against `min(the display's long edge, the requested edge)` now.

The setting does not reach 15 px text on an unscaled monitor (4 of 16 at every budget tried,
including 1982 tokens), does not help the 6 MiB ceiling (uniform noise reaches 6.50 MB at a 2048 px
capture), and was never the privacy argument. The measurement is the design input the `region` and
`display_index` fields were waiting for: what matters is source pixels per image token, so a region
wants a rectangle in the display's own physical coordinates, `display_index` is needed beside it
because a multi-monitor bounding box makes that ratio worse, and a window handle serves "read the
window I am looking at" better than a rectangle, since the body can resolve window bounds and the
model cannot.

The body half was done on 2026-08-10
([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) decision 16). The wire has
`CaptureScreenRequest.target`, a two-value `CaptureTarget` (`DISPLAY` = 0, which is the previous
behaviour exactly, and `FOCUS`), and the body honours it: the Windows backend resolves the focused
window by walking the desktop's Z-order, and pure core crops the frame. The field and the honouring
were one commit, because proto3 lets an older body ignore an unknown field, so a setting the
shipping body does not honour misreports a constraint the brain recorded as set. It also turned up
a live defect: `Capture` derived `source_width` and `source_height` from whatever frame it was
handed, so a cropped frame would have made the wire's `ImageBlob`, the brain's capture value and
`describe()`'s "downscaled from WxH" clause all report the window as though it were the screen. The
display's size and the crop's are separate now, with a test for it. Through the body's own crop and
encoder, a 1720x1200 text window of the 4K wallpaper desktop costs 43450 B untouched where the same
desktop whole costs 1978393 B resampled to 2048 px: forty-five times fewer bytes, every source
pixel kept, and no exposure to the halving ladder.

A rectangle the model names was declined. With the source size in front of it, the shipped cortex
declined on 3 of 47 strings and invented the other 38, so a model that does not report an
unreadable screen will not decline to name a rectangle either, and a wrong rectangle costs a second
OS receipt and a second tainted read of the wrong part of the screen. It reopens the day something
can hand the model a coordinate frame it did not guess, which would be an overlay-drawn region
picker, making the rectangle user-authored and so a privacy improvement. `TargetRect` is already
the value such a picker would produce.

The brain half followed the same day: `capture_screen` takes a required `target`, the model picks
it from a schema derived from the domain enum, and `describe()` renders a window as a crop out of
the display. Two things that half turned up. The accurate sentence needed a reply field, because
`source_width` and `source_height` are the display's on both paths, so a crop and a shrunk screen
are the same blob and the brain could not tell them apart. `CaptureScreenReply.resolved_target`
fixes that, read off what the body encoded rather than off the request, and it includes the target
and not the rectangle. And the free cap is two captures per target rather than two per loop,
because identity in `tool_salience.py` is name plus arguments, so the ceiling is four per loop. It
is four rather than six because a call naming no target is refused before the body is reached, and
four rather than unbounded because no synonym of a target is accepted. The number is asserted in a
test.

One input to a decision changed without changing the decision, recorded at the ADR: capture ships
without a confirmation card partly because a card could not describe what would be captured, the
call taking no arguments. It takes one now. The other three reasons are untouched.

The closing measurement ran the same day (ADR-0029 decision 17, readings in
[vision-capture](../../readings/vision-capture.md)): five desktops, 47 ground-truth strings, both
variants in one session on one server at the shipped budget and capture edge, three runs at
temperature 0. The 15 px row this entry was named for goes from a flat 5 of 12 on the shrunk screen
to 9 or 10 of 12 on the crop, and the clean case inside it is the 100% scaled terminal, 2 of 7
against 5 of 7 in every run, where the shrunk screen declined on the five it missed and the crop
transcribed them exactly. Three things temper that. Over all 47 the crop reads worse (29 to 31
against 32 to 33), because it cannot see the five strings outside the window, so pointing at a
window is a trade. On the 42 strings both variants contain, everything above 15 px is level or a
string or two worse on the crop, which at five or six strings a row is noise but is not the
predicted direction. And the one window wider than the capture edge (2400 px) is resampled to the
same 2048x1152 the screen is and reads no better, which says the mechanism is not being resampled
rather than being cropped.

The legibility corpus used on 2026-08-06 was a scratch script and was never committed, so it was
rebuilt to the same shape at `brain/packages/inference/tests/desktop_corpus.py` and the control
re-run: no number here may be compared against the 2026-08-06 table. The transcription of the
body's crop and downscale was proven equal to the Rust rather than eyeballed, with four cases
through `Capture::from_bgra`, the PNG decoded back to pixels and checksums identical.

`display_index` is now part of the multi-monitor entry
([262](262-multi-monitor-dpi-reporting.md)). A new cross-check opened beside this work, the proto
enum against the schema strings the model reads, recorded in
[repo-checks.md](../index.md#repo-checks).

## History

- 2026-07-18: Recorded when the vision slice was finished, as its headline risk, with the advice to
  take the deployment flag first and measure before spending the `display_index` and `region` proto
  fields.
- 2026-07-19: A bookkeeping pass found this one bullet had been counted as two names, region and
  window capture and legibility at 4K.
- 2026-08-06: The deployment flag was taken and measured, and legibility at 4K stopped being an
  open item. What closed was a risk rather than a piece of work, so the entry stayed open for the
  residue the setting does not reach.
- 2026-08-10: The body half was added. The model-named rectangle was declined inside the entry.
- 2026-08-10: The brain half followed later the same day, leaving nothing left to build here.
  `display_index` is counted under multi-monitor reporting instead.
- 2026-08-10: The measurement ran later still and closed the entry, on a measurement rather than a
  win. The rebuilt corpus is in the tree this time, at
  `brain/packages/inference/tests/desktop_corpus.py`.
- 2026-08-10: Correcting the shipped tool description against that measurement opened a new entry
  rather than reopening this one.
