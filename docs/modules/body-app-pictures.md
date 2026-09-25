# Module: the composer's attached pictures

**Purpose.** Lets the user attach up to four pictures to a message in the overlay and sends them
to the brain with the text, as [ADR-0070](../adr/ADR-0070-user-attached-images.md) decisions 5 and
7 describe. It lives in `body/app/src/overlay/` and `components/Composer.tsx`, and belongs to
[body-app.md](body-app.md).

## Public contract

- `pictures.ts` is pure: the limits (`MAX_ATTACHED_IMAGES`, `MAX_IMAGE_BYTES`,
  `DEFAULT_MAX_EDGE`), `fitted(width, height)` for the downscaled size, `pictureProblem(image)` for
  the brain's own size checks, `addPictures` for the count, and `readPictures(files, reader)`,
  which reads what it can and names the last problem met.
- `PictureReader` is the port that turns a file into an `AttachedImage` and a thumbnail address.
  `canvasPicture.ts` is its adapter: `createImageBitmap` decodes, a canvas downscales to a
  1600 px long edge and encodes JPEG as JPEG and anything else as PNG, and an 88 px canvas copy
  becomes the thumbnail as a data URL. jsdom has no canvas, so it is excluded from coverage and run
  in headless Chromium; tests inject a fake reader through `useOverlay`'s third argument.
- `pictureState.ts` holds `OverlayState.pictures`: the waiting pictures keyed by session id, the
  note shown above them, and the text and pictures of the turn in flight. The reducer handles
  `attach` and `detach`; `submit` moves the pictures into the turn; a `failed` event with code
  `attachment_refused` hands them back.
- `Composer` takes pictures from `paste` on the field and `drop` on the pill, claims a drag only
  when it holds files, and shows each waiting picture as a thumbnail with a remove control.
- `TauriBridge.converse` sends each picture's bytes as base64 in the `images` argument, which the
  shell's `converse` command decodes (`src/bridge/base64.ts`).

## Invariants

- A refused turn leaves no trace in the log: the user message and the reply bubble are removed,
  and a new chat's title goes back to "New chat". Text typed during the turn is kept over the sent
  text, and pictures attached since are added after the sent ones.
- Any other end of a turn drops the sent pictures; nothing holds them after the turn.
- `MAX_ATTACHED_IMAGES` and `MAX_IMAGE_BYTES` equal the brain's, and `DEFAULT_MAX_EDGE` equals the
  capture path's in `screen_policy.rs`; `scripts/wirecouplings.py` checks all three.
- The composer stacks into two rows while it shows pictures or a note, and `--pill-floor` on the
  view grows by their height, so the roll-open sections yield the room rather than the field.

## Dependencies

The `BrainBridge` port (`AttachedImage`), the drafts in `drafts.ts`, and the webview's
`createImageBitmap` and canvas. The demo bridge refuses the last picture of a prompt that says
"refuse", so the headless overlay shows the refusal state.
