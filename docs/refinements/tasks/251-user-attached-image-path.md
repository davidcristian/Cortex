# The user-attached image path

**Status:** done 2026-09-25
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

The user attaches a picture in the overlay and asks about it. The design is
[ADR-0070](../../adr/ADR-0070-user-attached-images.md). The brain reads `UserTurn.images`
(`cortex_orchestrator/attached.py`), refuses a bad one with `SeamError{code="attachment_refused"}`
before the turn starts, and sends the pixels on the working copy of the user's message while the
store keeps the text and a note. The body takes pictures by paste or drop into the composer, reads
each in the webview's canvas (`overlay/canvasPicture.ts`), and sends it through the bridge, the
shell's `converse` command and `BrainRpcClient::converse` into `UserTurn.images`.

## History

- 2026-07-18: Recorded when the vision slice was finished, from ADR-0029's own list of deferrals.
- 2026-08-09: A costing pass corrected the entry's closing line: it is blocked by the three-layer
  invariant above rather than by scope, and it must answer the persistence question rather than
  inherit an answer.
- 2026-09-13: Checked against the code. Every claim holds, and the four citations had all moved, so
  they name symbols instead of line numbers now. Nothing reads the field: `converse_stream.py`
  takes `event.user_turn.text` and nothing else, the overlay has no attachment path, and the two
  in-code notes about this deferral point at this backlog rather than at a coming slice.
- 2026-09-25: The design became ADR-0070 and the brain half was built. Of the three invariant
  layers only `Message` relaxed, to allow images on `USER`; the handoff snapshot and both session
  stores still refuse pixels. Filed [730](730-measure-the-attachment-frame-on-the-real-cortex.md)
  for the live run and [731](731-refuse-an-attachment-the-cortex-cannot-see.md) for a blind
  cortex. The entry stays open for the body half.
- 2026-09-25: Done. The body half was built through every layer: the transport port and gRPC client
  take the images, the Tauri command decodes them from base64, and the composer takes pictures by
  paste or drop, shows removable thumbnails, and gets a refused turn's text and pictures back.
  What follows is host item [024](../../host/tasks/024-attached-picture-over-ipc.md), the paste
  over real Tauri IPC, and [730](730-measure-the-attachment-frame-on-the-real-cortex.md), the live
  cortex run.
