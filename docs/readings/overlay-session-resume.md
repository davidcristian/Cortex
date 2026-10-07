# Readings: chats and appearance across a restart, and a chat past its history window, on the Linux shell

What the overlay showed when the shell was restarted with stored chats and stored appearance
choices, when the shell started before the brain, and when one chat grew past the brain's history
window. Cited by [ADR-0032](../adr/ADR-0032-preference-record.md). The procedure is the Linux
section of [the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless), and
the turns that end early are in [overlay-turn-flows.md](overlay-turn-flows.md).

## The rig

**2026-10-07**, a debug build of the shell from the tree with the overlay embedded
(`tauri/custom-protocol`), WebKitGTK drawing in software on an `Xvfb` display, against a stack
built from the tree on the 24 GB card: the shipped cortex, Redis, and
`docker/docker-compose.memory.yml` adding Postgres and the CPU embedder, all under their own
project name. Every key and click came from `xdotool`, every frame from `ffmpeg -f x11grab`, and
the stored chats, preferences and recap were read from Redis.

## Appearance across a restart

- **Brain up at the shell's start.** Midnight, Tangent and Still were picked on the console's Face
  tab, and Redis held `overlay.theme`, `overlay.mark` and `overlay.window` with those values. The
  shell was stopped and started again, and the first summon drew the panel in all three.
- **Brain down at the shell's start.** The shell was started with the brain's container stopped,
  and the brain 8 s later. It was healthy before the first summon, and the link dot was green, but
  the panel drew the default theme, mark and edge on that summon and on the next one: the record
  was read once at mount, while the brain could not answer. With the overlay reading it again on
  each summon until a read succeeds, the same sequence drew Midnight, Tangent and Still at the
  first summon.

## Chats across a restart

- **The newest chat is restored.** Two chats were stored and the shell restarted with the brain
  up. The first summon opened on the newer chat, its question and answer drawn from the store with
  no `Thoughts` disclosure, since a trace is not stored.
- **An older chat resumes.** The switcher listed both chats with their last replies. A click on
  the older one opened it, and a follow-up asking for the boat's name and pier, given only in that
  chat's first turn, was answered with both.
- **Brain down at the shell's start.** With the brain started 8 s after the shell, each summon
  opened on `New chat` while the switcher listed every stored chat, in both runs, before and after
  the appearance fix ([R-818](../refinements/tasks/818-a-body-started-before-the-brain-opens-a-new-chat.md)).

## A chat past its history window

The shipped window keeps 24,000 characters of a chat's history and folds what it drops into a
recap the cortex writes. One chat told the cortex a locker code and wing in its first turn, then
asked for five essays of about 1200 words each. Its stored records came to 28,210 characters
after the third essay and 46,936 after the fifth.

- **The recap.** After the last turn the chat's stored recap covered its first eight messages,
  the first turn and the first three essays, and its first sentence was the locker's code and
  wing.
- **The fact survives.** Asked for the code and the wing after the fifth essay, the cortex
  answered both. The overlay drew the whole chat throughout and showed nothing when turns left the
  window.
- **The log stopped following.** In this one chat the conversation stayed scrolled to its first
  message through all five essays and the last answer, so none of the replies could be seen
  without scrolling. Reopened from the switcher in a later shell, the chat opened on its end and
  followed its next reply. Four other chats each followed their essay: one in the same shell, and
  three in shells started with the brain up or down, with or without a hide before the first turn
  ([R-819](../refinements/tasks/819-the-conversation-stopped-following-the-replies-of-one-chat.md)).

Method: `measurements/session-resume-2026-10-07/`, with the scripts that ran the shell and the
stack, `longchat.sh` the long chat and its log, `repro.sh` and `repro2.sh` the fresh chats, frames
in `shots/` (`A-*` the picks, `B-*` the restart, `C-*` and `D-*` the brain started late before and
after the fix, `E-*` and `F/` the long chat, `G/`, `H*`, `I-*` and `J1-*` the follow runs), the
stored recap and preferences, and the brain's and the model host's logs.
