# A paused stream keeps its last letters blurred

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md) decisions 2 and 5
**Trigger:** a History line in this file recording the maintainer's pick of a pause signal, a finish
and a rule for the last word, from the three choices in the proposal.
**Verified:** 2026-10-06

The whispered reply condenses letters on a front that trails the arrivals, and a letter inside the
nine-letter band (`BAND_LETTERS` in `body/app/src/whisper/front.ts`) holds part opacity and blur
from `rampAt`. While the turn streams, `goalOf` stops the front at the letters `confirmedOf`
allows, the end of the last word some whitespace has followed, and only the settle runs it a band
further. So when a turn is still streaming but no text arrives, the eight letters before the front
stay part condensed and the word after it stays at opacity zero (decision 5).

In a handoff that pause is the whole swap. In the overlay run on 2026-10-06 the cortex's sentence
ended "odd numbers eq" and a blur where the text was "odd numbers equals $n^2$.", from the loading
line until the deep model's first text, minutes later
([readings](../../readings/model-swap.md#the-overlays-view-of-a-handoff), and the frame
`measurements/overlay-handoff-2026-10-06/08-loading.png`).
Nothing followed "$n^2$." until the deep model's text, so decision 5 held it hidden through the
swap; the paragraph break that now opens that text also arrives after the swap. A tool call that
takes long, or a confirm card left open, pauses the stream the same way.

## Proposal

The fix is new motion inside decisions the maintainer picked by eye, so it is a pick. Each choice
below names its recommendation; any combination works.

1. **What starts a pause.**
   - **Recommended: an event.** The bubble latches the message's `status` and `tool` and treats a
     change to either while `content` has not grown as a pause; the next text ends it. A tool
     chip, every handoff status line, the deep model's reasoning and a heartbeat naming a new wait
     all change one of them, so the paced, not timed rule of decision 2 holds.
   - Alternative: a quiet interval, such as no text for three times `CATCHUP_SECONDS`. It also
     catches a pause no event announces, but it is a timer, and it would close the band mid
     sentence whenever the cortex generates slowly, so ordinary streaming would look different on a
     slower card.
2. **How the band finishes.**
   - **Recommended: the band closes behind a front that stays.** The letters behind the front
     condense to ink at the drain's pace while the front and the mist stay where they are, and
     `s.lo` in `whisper/useWhisperClock.ts` moves to the front, so those letters stay finished. On
     the next text the band forms again from the front, and no letter is blurred again or appears
     as a block.
   - Alternative: the front runs a band past the end, as the settle does, with the held letters
     kept at zero. It reuses the settle's motion, but on the next text up to eight new letters
     appear at once at part opacity, which decision 2 rules out.
3. **The last word.**
   - **Recommended: the brain completes it.** The escalating engine in
     `brain/packages/core/src/cortex_core/escalating_engine.py` sends the paragraph break as its
     own text when the cortex phase ends, before the swap, instead of opening the deep model's
     first text with it, and a swap note then drops its own opening blank line. Decision 5 stays
     as it is, and the handoff's last word condenses with the band. A tool call's pause still
     holds its last word.
   - Alternative: a pause releases the last word, as the drain does. Every pause then shows
     everything received, but text that resumes inside that word grows a visible word, which can
     wrap to the next line, against decision 5.
   - Alternative: keep holding it, so a paused sentence shows up to its last whitespace.

The recommended set edits ADR-0037 decision 2 with the pause and adds the engine's break to
[ADR-0030](../../adr/ADR-0030-brain-handoff.md). The cost is a `paused` fact for the clock,
derived in `components/WhisperBubble.tsx`, a band-closing branch in the clock's frame, and their
tests; `useWhisperClock.ts` has 264 of its 300 lines.

## History

- 2026-10-06: filed by the overlay's view of a handoff on the Linux shell
  ([H-018](../../host/tasks/018-tier-scale-swap.md)); the fix is a motion pick, so it is a proposal
  that waits for the maintainer.
