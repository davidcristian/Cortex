# A live vision probe

**Status:** done 2026-08-06
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

The `/props` vision probe ran once at startup. A `llama-server` restarted without `--mmproj`
mid-session left `capture_screen` advertised, so a capture would be taken, the user notified and
the turn tainted for an image the model cannot read: the full privacy cost for no benefit.

Closed 2026-08-06 ([ADR-0029 decision 13](../../adr/ADR-0029-vision-screen-capture.md)). The
failure was reproduced end to end against the real stack first: a `model-host` recreated without
`CORTEX_MMPROJ_FILE_CORTEX` flipped `/props` from `vision: true` to `vision: false` under a brain
whose container never restarted and whose log still held exactly one probe line, and the next "look
at my screen" read the screen, showed the capture receipt, tainted the turn and died on llama.cpp's
`image input is not supported - hint: ... you may need to provide the mmproj`.

The fix the entry proposed, re-probing when a swap changes residency, was the wrong one. A child's
argv is fixed when the sidecar boots, so a swap's `stop` then `start` respawns the cortex tier from
the same flags: driven directly against the running control API, `/props` answered `vision: true`
before and after. That event cannot change the answer, and the event that does change it does not
touch residency.

What shipped instead is a port asked at the two moments the answer is acted on, with no caching.
`VisionProbe.can_see()` never raises and returns False when it cannot tell; `SightedToolRegistry`
leaves `capture_screen` out of the advertisement and refuses it at the call, which is the half that
protects the user, since a turn lists its tools once and then runs rounds against that list. Not
caching is affordable by measurement: `/props` answers in 1.5 ms idle and 1.7 ms with a generation
in flight (worst of 40 samples 2.5 ms) against a capture that blits and PNG-encodes a display, so
the probe's timeout came down from 5 s to 2 s now that it sits inside a turn. The entry's objection
was also wrong: `vision.py` has always lived in the composition root, never in `cortex_inference`,
so re-probing never made the inference adapter stateful. One thing came free: the advertisement now
corrects itself in both directions, so a deployment that gains a projector after boot no longer
waits for a brain restart.

## History

- 2026-07-19: Recorded as no longer hypothetical, since the real swap restarts model servers.
- 2026-08-06: Closed. Its cost was reproduced end to end and held, while the event it named as the
  trigger was disproved, which is worth recording beside the cost estimates this backlog already
  warns about: an entry can name the right defect and the wrong trigger.
