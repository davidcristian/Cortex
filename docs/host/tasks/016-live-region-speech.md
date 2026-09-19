# What the live region is spoken as

**Status:** never attempted
**Session:** overlay-screen-reader
**Capability:** W
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

The overlay's real deployment is the Tauri window on a Win32 desktop, and the readers that matter
(NVDA, and JAWS if it is to hand) run there. The dev machine is Linux under WSL2, and while headless
Chromium hands over the full accessibility tree, no tree says what a reader will *speak*.

This is one observation session rather than a pass or a fail. What it produces is a recording of
what was heard, in order, which is the one thing the automated checks cannot produce. It uses the
same bring-up as the Windows desktop session and can be folded into it if NVDA is already
installed; it is kept separate because it needs a reader and a speech viewer.

## What only this proves

The overlay's announcements are covered to the last attribute on the agent's own machine. Every live
region on the page, its `live`, `atomic` and `relevant` values, the exact text it holds before and
after each gesture, and the fact that each gesture mutates exactly one of them, were all measured in
Chromium over `Accessibility.getFullAXTree` plus a `MutationObserver`, and the sentences it holds
are [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md) decisions 12 to 15. What is
left is the half a tree cannot hold: **speech**. A polite region is a request to the reader, and
each reader applies its own rules for whether to voice it, when, and what to do when something else
is competing for the same moment.

One case is the reason this is a session rather than a curiosity. **Deleting the chat that is open
shrinks the list and swaps the conversation in one commit**, and the same commit moves the caret
into the composer. So a focus change and a polite live-region update happen together, and the two
plausible outcomes are opposite: the reader speaks the region and then the newly focused field, or
the focus announcement wins and the sentence about the list is dropped. If it is dropped, the
sentence needs to be somewhere else.

## Bring-up

The [windows-desktop.md](../index.md#windows-desktop) bring-up, unchanged, plus a reader:

- NVDA (free, and the one most Windows users have) with speech viewer on, which gives a written
  transcript of everything spoken and is what makes the result recordable rather than remembered.
- Optionally JAWS, and optionally VoiceOver on a Mac once the shell builds there, since a
  disagreement between two readers is itself a finding.

Seed the session so the gestures are available: at least three stored chats, and at least two
fired-but-undelivered reminders (the same seeding
[windows-desktop.md](../index.md#windows-desktop) checks 2 and 5 need).

## Do, and what to write down

Run each gesture with the speech viewer open and paste what it said. The right-hand column is what
the region holds, measured, not a prediction about speech.

| Gesture | The region should hold |
| --- | --- |
| `Ctrl+↓` to cycle a chat | `Switched to <the arriving chat's title>.` |
| A switcher row, which is bound silent | nothing new |
| Delete a chat that is not the one open | `Chat deleted. 2 chats left.` |
| Delete down to the last one | `Chat deleted. No other chats yet.` |
| **Delete the chat that is open** | `Chat deleted. 1 chat left. Switched to New chat.` |
| Ack a reminder | `Reminder dismissed. 1 reminder left.` |
| Ack the last reminder | `Reminder dismissed. No reminders left.` |
| `Ctrl+K` from the composer to open the list | `Recent chats open. 3 chats.` |
| `Ctrl+K` again to close it | nothing new |
| The header's chats button, which is bound silent | nothing new, and the button's own `expanded` |
| `Ctrl+K` with every other chat deleted | `Recent chats open. No other chats yet.` |
| `Ctrl+N` inside an open rename editor | nothing, deliberately |

The four questions the transcript answers:

1. **Is each sentence spoken at all**, and is it spoken once rather than twice (the region's child
   is replaced rather than edited, which is one mutation and should be one utterance).
2. **The open-chat delete**: is the sentence spoken beside the composer's focus announcement, in
   which order, and is any part of it lost.
3. **Is the whole sentence read**, or does a reader cut a three-clause polite update short.
4. **Does anything speak twice**, which would mean the region and some other channel are both
   reporting the same change. There is one case where the design expects it and accepts it:
   `Ctrl+K` pressed with the caret parked on the chats button, where the button's own `expanded`
   flips under the reader and the sentence arrives as well. If a reader stutters there, note it; the
   alternative is asking the DOM where the caret is from inside a reducer, which the ADR rejected.

Three things to note in passing while a reader is on the overlay, since the bring-up is the
expensive part: whether the switcher reads as a list of rows with their four buttons per row (the
listbox role came off for exactly this reason), whether the caret's landings after a row gesture
read as the controls they are (`Delete <title>`, `Cancel delete`, `Recent chats`, the composer), and
whether a reader inside the rename editor can tell the held `Ctrl+N` from an application that has
stopped answering. That last silence is a decision rather than an omission, argued in the same ADR
on the grounds that the hold destroys nothing and that the branch it is decided at cannot tell a
bound chord from `Ctrl+Z`; a reader who is genuinely stranded there is the finding that reopens it.

## Pass looks like

Every sentence in the table spoken once, in full, and the open-chat delete's sentence surviving
alongside the composer's focus announcement in some order. Per [index.md](../index.md)'s warning,
that is what the design expects rather than what will happen; a transcript that contradicts it is
the more valuable result.

## Fail, and what each failure means

- **Nothing is spoken anywhere.** The region is not being seen at all. Check it is in the tree
  before the words arrive (it is rendered at the overlay's root and never remounts, which is
  covered by tests), then suspect the WebView2 accessibility bridge rather than the overlay.
- **The list sentence is lost only on the open-chat delete.** The focus change wins the moment. The
  fix is a decision rather than a bug: either the sentence moves off that commit, or the delete
  stops taking the caret with it, or the region goes assertive for that one case. Record which
  reader, and record whether the arrival half survived.
- **A three-clause sentence is cut short.** Split it, or shorten it. The clause order was chosen so
  the delete leads and the arrival follows; if only the head survives, that ordering was right and
  the ADR should say so.
- **Something is spoken twice.** Look for a second channel: a focus move onto a control whose name
  contains the same words is the likely one.

## Record it

Put the transcript in the readings record under [docs/readings/](../../readings/README.md) that
[ADR-0035](../../adr/ADR-0035-console-and-motion.md) rests on, and edit that ADR in place where the
run changes what it states about the live region. If the open-chat delete loses its list sentence,
the ADR is also where the replacement is argued, and a new entry goes in the refinements backlog's
body-overlay area for the work. Then delete this section, per the exit contract in
[index.md](../index.md).

## History

- 2026-08-07: added when the overlay's live region learned to report a list that shrank and the tree
  stopped being able to answer the last question about it.
- 2026-08-07: the host index sizes this session at eight gestures in both places that give it a
  size, while the gesture table above lists twelve rows. Both counts are kept rather than one
  picked. The index also files it under "W, each with its own bring-up" while its recommended order
  says it uses the same bring-up as the Windows desktop session; both readings are the index's own
  and both are kept.
