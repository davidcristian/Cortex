# An attached picture through real Tauri IPC

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md)
**Verified:** 2026-10-06

Narrowed 2026-10-06 to the two ways in that WebView2 owns. On the Linux shell, pictures handed to
the composer's paste handler went through the canvas reader, the base64 `images` argument of the
shell's `converse` command and the shell's decode into the brain: two thumbnails showed, the reply
described both, a reopened chat showed the brain's `(Attached to this message and not kept: ...)`
note, and a brain that could not see refused the turn with the question and both pictures handed
back ([readings](../../readings/tauri-ipc-commands.md#attached-pictures-and-reminder-cards)). That
path has no Windows code. The same run showed that a file named `.png` holding JPEG bytes is
attached and accepted, not refused: the canvas encodes it again as PNG before it is sent.

**What only this proves.** That WebView2 hands the composer a `File` for a picture pasted from the
Windows clipboard and for one dropped from Explorer. WebKitGTK gives neither
([R-802](../../refinements/tasks/802-the-linux-shell-attaches-no-pasted-or-dropped-picture.md)),
so the Linux run built its paste in the page. The drop cannot pass yet: under the shipped window
config, Tauri's native drop handler takes every Explorer drop before the page sees it
([R-801](../../refinements/tasks/801-a-dropped-file-never-reaches-the-composer.md)).

**Do.** Once R-801 is done, with the brain up and a vision-capable cortex, copy a screenshot
(Win+Shift+S), paste it into the composer with Ctrl+V, drop a JPEG from Explorer beside it, type a
question and send it. Then drag a link from a browser over the window and let go.

**Pass.** Two thumbnails show and the reply describes both pictures. The dragged link changes
nothing: the window stays on the overlay.

**Fail.** A paste that inserts nothing is WebView2 offering the screenshot in a format it does not
give the page as a file. A drop that does nothing, or that navigates the window to the file or the
link, is the drop handling R-801 names.

**Record it.** Edit [ADR-0070](../../adr/ADR-0070-user-attached-images.md) in place where it names
this as pending; then delete this section.

## History

- 2026-09-25: Filed when the overlay half of the attached-picture path was built, since only a
  Win32 desktop has the clipboard and the WebView2 drop target this needs.
- 2026-10-06: narrowed after the Linux shell run sent pictures through the real IPC hop into the
  brain. The run filed [R-801](../../refinements/tasks/801-a-dropped-file-never-reaches-the-composer.md),
  [R-802](../../refinements/tasks/802-the-linux-shell-attaches-no-pasted-or-dropped-picture.md) and
  [R-804](../../refinements/tasks/804-the-picture-note-follows-the-user-to-another-chat.md), a
  refusal's sentence left over the composer of the next chat.
