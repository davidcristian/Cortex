# The picture note follows the user to another chat

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md) decision 7
**Verified:** 2026-10-06

`PictureState` in `body/app/src/overlay/pictureState.ts` keeps the waiting pictures per chat
(`waiting`, keyed by session id) but one `note` for the whole overlay. Nothing clears the note when
the chat changes, so a refusal's sentence, or a "could not be read" line, stays over the composer
of a chat that holds no pictures. On the Linux shell, after a refused turn, `Ctrl+N` opened an
empty chat that still showed "the attached pictures were refused" over no pictures
([readings](../../readings/tauri-ipc-commands.md#attached-pictures-and-reminder-cards)).

**Do.** Key the note by session id beside `waiting`, so it leaves with its chat and comes back
when the user returns to the chat whose pictures it describes, as a draft does. Cover the switch
both ways in `pictureState.test.ts`.

## History

- 2026-10-06: filed by the Linux shell run of the attached-picture path.
