# Region and window capture, and legibility at 4K

**Status:** landed 2026-08-10
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

The headline risk. The projector tiles to
a bounded token budget (measured: 266 tokens for anything from 720p up), so a 4K desktop
downscaled to 1600 px may render small text unreadable. Expect layout-level answers to be good
and small-text answers unreliable. The **first** mitigation is a deployment flag with no code
at all, llama.cpp's `--image-max-tokens`; the real fix is capturing a region or a window rather
than a bigger PNG, which needs the `display_index`/`region` proto fields ADR-0029 deliberately
refused to add without a consumer. The `CaptureRequest` value already carries the shape.

**Measured 2026-08-06, and the risk is real, the mitigation is real, and the entry was wrong
about the mitigation being free**
([ADR-0029 legibility addendum](../../adr/ADR-0029-vision-screen-capture.md)). Five synthetic
3840x2160 desktops carrying 47 ground-truth strings from 15 px to 52 px (a code editor, a
terminal, a browser article, a spreadsheet in its usual grey, a chat client; light and dark; 150%
scaling and 100%) were put through a transcription of the body's own `box_filter`, proven equal
to the Rust loop, and read by the shipped cortex through the shipped request scaffold. The
shipped deployment reads **6 to 8 of 47**, the flag alone reads **24 to 26**, and the flag with
`CORTEX_BODY_CAPTURE_MAX_EDGE=2048` reads **36 to 38**, against a 400 px control at 2. So the risk was
not overstated and the knob answers most of it: 13% to 79% for about 400 MiB of VRAM, 0.6 s of
time to first token, and 744 context tokens a capture.

Four things the entry did not have. **The flag was not reachable**: `ModelHostConfig` builds the
cortex tier's argv and had no way to pass it, so "a deployment flag with no code at all" was a
hypothesis about a deployment nobody had tried it on. **The flag alone crashes the server**: a
picture is one non-causal chunk and llama.cpp asserts the micro-batch covers it, so a raised
budget without `--ubatch-size` aborts `llama-server` with SIGSEGV on the first oversized picture,
met in anger on the second command of the sitting. Both are now one knob,
`CORTEX_IMAGE_MAX_TOKENS`, emitting the pair. **A bigger PNG buys nothing**, which
the saturation predicted and this confirms as a legibility fact (4 of 47 at a 3072 px capture on
the shipped budget), and a full-resolution capture at the raised budget is *worse* than a 2048 px
one on identical tokens, because the encoder's own resize is a poorer filter than the body's box
average. And **the model does not decline**: with `describe`'s source size in front of it and
"unreadable" offered as an answer, the shipped deployment declined on 3 of 47 and invented the
rest, which narrows a claim that docstring has made since the slice landed.

**The pair is the default from 2026-08-06 on** (ADR-0029's legibility addendum, "the default
moved"), which is the one sentence this entry used to leave open: the measurement said the
recommendation was the maintainer's to take, and the maintainer took it the same day.
`CORTEX_IMAGE_MAX_TOKENS=1024` and `CORTEX_BODY_CAPTURE_MAX_EDGE=2048` are what an unconfigured
seeing stack now comes up with, both still refundable to `0`. Turning it on cost one measurement
this entry had been carrying as an open worry rather than a number: whether a real screen at
2048 px fires the halving ladder. Through the body's own downscaler and encoder, a 4K frame costs
243 KB as a text desktop, 1.98 MB as a wallpaper under two windows, 3.59 MB as a full-screen
photograph and 4.67 MB with heavy grain over it, so the worst realistic screen sits at 74% of the
ceiling and only per-pixel noise crosses it
([`capture_bytes.rs`](../../../body/crates/core/tests/capture_bytes.rs)).

**That 74% was a 4K number, and 4K is not the costly case** (measured 2026-08-06, the same
harness). How much grain survives is decided by the ratio between the display and the requested
edge, not by either alone: a 4K screen averages three and a half source pixels into every output
pixel and most of the grain dies there, while a display nearer 2048 px averages almost nothing. A
2560x1440 desktop under the same heavy grain costs 5.02 MB against 4K's 4.67 MB, so **the worst
realistic screen is 79% of the ceiling rather than 74%**, and the ladder fires one step of grain
earlier there than at 4K. A 1920x1080 desktop is cheaper again at 71%, because it is already
inside the requested edge and crosses the seam untouched, and fewer pixels beat undiluted grain.
The margin is smaller than the closing measurement said and it still holds: nothing a person
would look at fires the ladder at the shipped default. Correcting this also corrected the
harness, whose verdict compared the returned width against the *requested* edge and so read an
untouched 1920x1080 capture as a fired ladder; it compares against
`min(the display's long edge, the requested edge)` now.

**The fields are demoted, not declined, and the entry stays open.** The knob does not reach 15 px
text on an unscaled monitor (4 of 16 at every budget tried, including 1982 tokens), it does not
help the 6 MiB ceiling (uniform noise reaches 6.50 MB at a 2048 px capture and fires the halving
ladder, and a full 3840 px capture fires it on a photograph alone), and it was never the privacy
argument. Raising the default has if anything sharpened the first of those: the deployment now
spends 1010 tokens and 744 context tokens a capture on a whole screen, which is exactly the
budget a region would spend on the part of it the user asked about. The measurement is the
design input the fields
were waiting for: the binding quantity is **source pixels per image token**, so `region` wants a
rectangle in the display's own physical coordinates rather than a normalized one, `display_index`
is required beside it because a multi-monitor bounding box makes that ratio worse, and a window
handle would serve "read the window I am looking at" better than a rectangle, since the body
knows window bounds and the model cannot express them.

**The body half landed 2026-08-10, and the rectangle was declined**
([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)'s addendum of that date). The seam carries
`CaptureScreenRequest.target`, a two-value `CaptureTarget` (`DISPLAY` = 0, which is today's
behaviour exactly, and `FOCUS`), and the shipping body honours it: the Windows backend resolves
the focused window by walking the desktop's Z-order, and pure core crops the frame to what it
found. The field and the honouring landed in one commit because that is what this entry's own
blocker actually said. "The fields ADR-0029 deliberately refused to add without a consumer" was
the wrong reading of the refusal, which was never about a caller: proto3 lets an older body
ignore an unknown field, so a knob the shipping body does not honour is a **silent lie** about a
constraint the brain believes it set, and the 2026-07-18 correction admitted `max_bytes` on
exactly that basis. A brain that asks is the next commit, and it is why this entry stays open.

**The estimate this entry carried was wrong in the cheap direction, for once.** "A seam change
with a design attached rather than an increment" priced the whole thing; the body half is one
proto field, one enum, one value type, a crop folded into the existing downscaler, a second
receipt sentence, and a Z-order walk. What it also turned up is a live trap the entry did not
have: `Capture` derived `source_width`/`source_height` from whatever frame it was handed, so a
cropped frame flowing through would have made three consumers (the wire's `ImageBlob`, the
brain's own capture value, and `describe()`'s "downscaled from WxH" clause) report the window as
though it were the screen. The display's size and the crop's are separate now, pinned by a test
written for that one thing.

**What a window is worth, in bytes.** Through the body's own crop and encoder, a 1720x1200 text
window of the 4K wallpaper desktop costs **43450 B untouched** where the same desktop whole
costs **1978393 B resampled to 2048 px**: forty-five times fewer bytes, every source pixel of
the part that was asked about kept, and no exposure to the halving ladder. Every previously
recorded row of [`capture_bytes.rs`](../../../body/crates/core/tests/capture_bytes.rs) came back
byte for byte identical after the downscaler moved, so the margins the legibility addendum
records are unmoved.

**A model-named rectangle is declined, uncounted, and reopens on one thing.** The entry's own
design input said `region` wants physical display coordinates; what it did not say is who names
them. The 2026-08-06 measurement above answers that: with the source size in front of it and
"unreadable"
offered as an answer, the shipped cortex declined on 3 of 47 strings and invented the other 38,
so a model that will not admit it cannot read a screen will not decline to name a rectangle
either. A wrong rectangle costs a second OS receipt and a second tainted read of the wrong part
of the screen. It reopens the day something can hand the model a coordinate frame it did not
guess, and the shape that does it is an **overlay-drawn region picker**, which makes the
rectangle user-authored and therefore a privacy improvement rather than a privacy widening.
`TargetRect` is already the value such a picker would produce.

**The brain half landed later the same day, and the entry is a measurement now**
([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)'s second addendum of that date). All three
things the body half handed forward are done: `capture_screen` takes a required `target`, the
model picks it from a schema derived from the domain enum, and `describe()` renders a window as
a crop out of the display rather than as a shrunk screen.

Two things that half turned up which the body half's own list did not have. The first is that
**the honest sentence needed a reply-side field**: `source_width`/`source_height` are the
display's on both paths, deliberately, so a crop and a shrunk screen are the same blob and the
brain could not tell them apart from the payload. `CaptureScreenReply.resolved_target` closes
that, read off what the body encoded rather than off the ask, which is the same predicate the OS
receipt is picked by, so the sentence the user sees and the sentence the model reads cannot
disagree about one picture. It carries the target and not the rectangle, because coordinates on
the reply would hand back the frame the rectangle decline just refused to take.

The second is the bound, and it is worse than the body half predicted and still defensible.
Decision 7's free cap was two captures a loop because every call was byte-identical. Read against
`tool_salience.py` rather than against the paragraph, identity is name plus arguments, so **each
target is its own identity and the ceiling is two per target, four a loop**. Four rather than six
is a property of the tool: a call naming no target is refused before the body is reached, so the
empty spelling costs a dispatch and takes no picture. Four rather than unbounded is the exact
match, since every accepted synonym would buy another two, which is the one place being strict
with the model is what buys the bound. The number is asserted out loud in a test rather than left
to be rediscovered.

One input to a decision moved without moving the decision, and is recorded at the ADR so the
maintainer can overrule it knowingly: capture ships **ungated** partly because a confirm card
could not describe what would be captured, the call taking no arguments. It takes one now, so a
card could promise the window or the screen. The other three legs are untouched and the gating is
unchanged.

**The measurement ran the same day, and it closes this entry**
([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)'s third addendum of 2026-08-10). Five
desktops, 47 ground-truth strings, both arms in one session on one server at the shipped budget
and capture edge, three runs at temperature 0. The 15 px row this entry was named for goes from
a flat **5 of 12** on the shrunk screen to **9 or 10 of 12** on the crop, and the clean case
inside it is the 100% scaled terminal, 2 of 7 against 5 of 7 in every run, where the shrunk
screen declined on the five it missed and the crop transcribed them character for character.
Three things temper it and are the reason the entry closes on a measurement rather than on a
win. Over all 47 the crop reads **worse** (29 to 31 against 32 to 33), because it cannot see the
five strings outside the window, so pointing at a window is a trade and the model makes it. On
the 42 strings both arms carry, everything above 15 px is level or a string or two worse on the
crop, which at five or six strings a row is noise but is not the predicted direction. And the
one window wider than the capture edge (2400 px) is resampled to the same 2048x1152 the screen
is and reads no better than it, which says the mechanism is **not being cropped** but being
**unresampled**: the earlier addendum's rule about keeping the region's long edge inside the
capture edge is the whole effect rather than a tuning note.

Two things the measurement turned up beside its number. The recorded legibility corpus was a
scratch harness and was never committed, so it had to be **rebuilt** to the same shape and the
control re-run rather than cited, and no number here may be read against the 2026-08-06 table.
And the transcription of the body's crop and downscale was proven equal to the Rust rather than
eyeballed: four cases through `Capture::from_bgra`, the PNG decoded back to pixels, checksums
identical, so `screen_image.rs` and the harness have not drifted.

`display_index` is no longer named here: it is
the multi-monitor entry below, which already carries it and already says the target spent the
field number it was being held for. A **new coupling** opened beside this landing rather than
inside it, the proto enum against the schema strings the model reads, and it lives with the other
couplings the constant scan cannot hold in [repo-gates.md](../index.md#repo-gates).

## Trail

- 2026-07-18: recorded in this area when the vision slice landed, as the slice's headline risk.
  The index's guidance was to take the deployment flag first and measure before spending the
  `display_index`/`region` proto fields.
- 2026-07-19: a bookkeeping pass found that the area's Open items line had reached its count by
  splitting this one bullet into two names, region and window capture and legibility at 4K, which is
  why the names outnumbered the bullets by one. Both names are stated in the area doc from that day.
- 2026-08-06: the deployment flag was taken and measured, and legibility at 4K left the Open items
  line, moving the area's count 15 to 14. What closed was a risk rather than a piece of work, so the
  bullet stayed and stayed counted for the residue the knob does not reach, and the two names that
  had shared it became one name.
- 2026-08-10: the body half landed and the count held at 11, since a cell decremented for a
  half-closed entry is how an open deferral gets lost. The model-named rectangle was declined inside
  the entry and stays uncounted, because a decline names no work until its trigger fires.
- 2026-08-10: the brain half landed later the same day, leaving nothing built-shaped in the entry,
  so its name changed rather than leaving and the count held at 11 again. `display_index` did not
  stay on the Open items line either, being counted already as multi-monitor reporting. The index
  also recorded that the entry had outgrown the pickup-order heading it was filed under, the seam
  change it waited on being done, and left it in place because the paragraphs there read in order.
- 2026-08-10: the measurement ran later still and closed the entry whole, moving the count 11 to 10.
  It closed on a measurement rather than on a win. The rebuilt corpus is in the tree this time, at
  `brain/packages/inference/tests/desktop_corpus.py`, the 2026-08-06 one having been a scratch
  harness whose numbers outlived it.
- 2026-08-10: correcting the shipped tool description against that measurement raised a field the
  landing deliberately did not build, so the count moved 10 to 11 on a new entry rather than on this
  one reopening.
