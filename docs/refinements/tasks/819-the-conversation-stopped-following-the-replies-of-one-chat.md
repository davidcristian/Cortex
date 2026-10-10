# The conversation stopped following the replies of one chat

**Status:** done 2026-10-10
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

On the Linux shell on 2026-10-07 one chat's conversation stayed scrolled to its first message
through five long replies and a short answer, all streamed while nobody scrolled
([readings](../../readings/overlay-session-resume.md#a-chat-past-its-history-window)). The person
saw none of those replies. Reopened from the switcher in a later shell, the same chat opened on
its end and followed its next reply, and four other chats, three of them in fresh shells, followed
theirs. The chat began right after a summon chord that hid the panel while a driver typed a
question and pressed `Enter` into the hidden window, which sent nothing, and a second chord that
showed it again.

`overlay/useLogScroll.ts` follows a reply only while its `onTail` flag is set, and only `onScroll`
changes that flag, from the box's position when a scroll event fires. A scroll event fired while
the content stood more than 40 px below the box would clear it, and nothing sets it again until
the reader scrolls back to the end. Which layout change fired that event is not known; the frames
start after it. The page code is the same in WebView2, so Windows may have it too; that is an
assumption, not run.

## What to do when it fires

Capture frames from the summon before the first turn, log `onTail` changes from the page, and
name the event that cleared it. A fix then either ignores a scroll event the reader did not make,
or sets the flag again when a new turn starts.

## History

- 2026-10-07: filed from the long chat run on the Linux shell, after three attempts to bring it
  back failed.
- 2026-10-10: the trigger fired on the Linux shell. A 300-word essay was followed to its end until
  the brain's container was restarted 7 s into it; the reply then drew the rest of its text and an
  error bubble below, and the log stayed on the middle of the essay with nobody scrolling, until it
  was scrolled by hand ([readings](../../readings/store-and-process-restarts.md#the-brain)). This
  run ended in an error, so it may be a second path to the same flag rather than the first one.
- 2026-10-10: done. A line the page drew at each scroll event showed the cause on the cut essay: the
  rest of the reply and the error bubble made the content 545 px taller in one render, and the
  scroll event queued by the last follow call then fired with the box unmoved, 545 px from the new
  end, and turned following off. `useLogScroll` now turns it off only when the box has moved from
  where the hook last put it or saw it. Two later cut replies ended on their end
  ([readings](../../readings/store-and-process-restarts.md#following-a-reply-cut-by-a-restart)).
  The hidden-window path of 2026-10-07 was not run again; that a scroll event held back while the
  window was hidden fired after the show with the box unmoved, which the same rule covers, is an
  assumption.
