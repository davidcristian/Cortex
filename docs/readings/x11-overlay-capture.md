# Readings: what an X11 capture shows of the overlay

Pixel counts of `CaptureScreen` replies from the linked Linux shell under the conditions a real X11
desktop adds to a bare `Xvfb`, of single windows read directly under a compositor, of the
capture built from those reads, and of the root background a compositor paints. Cited by
[ADR-0029](../adr/ADR-0029-vision-screen-capture.md) decision 10.

## Method

**2026-10-01.** `Xvfb` at 1280 by 800, depth 24, with a full-screen white window of type
`_NET_WM_WINDOW_TYPE_DESKTOP` under the overlay. The shell runs as the
[overlay runbook](../runbooks/body-overlay.md) says, with `CORTEX_HOST_CAPTURE=1`; an XTEST press
of the chord shows and hides the overlay, and `CaptureScreen` is called over gRPC with `max_edge`
1280. Each reply is counted as pure black, pure white and other pixels. A plain `GetImage` of the
root, taken right after each capture, is counted the same way and shows the overlay was on screen.
The overlay is 640 by 720 at 320, 40: 460,800 pixels, all of them "other" in a plain read.

openbox 3.6.1, picom 10.2 and xcompmgr 1.1.8 came from `apt-get download` and `dpkg-deb -x` into a
userspace prefix, as in the [shell clippy readings](shell-clippy.md), and ran without sudo. picom
used `--backend xrender -c`, and with fading `-f --fade-out-step 0.01 --fade-delta 50`, a fade of
about five seconds; xcompmgr used `-c -f -F -O 0.01 -D 50`. WebKitGTK was 2.52.6.

## Before the compositor refusal

"Fade" is a capture taken 0.3 s after the press that hides the overlay.

| Condition | Shown: black, other | Plain read, shown: other | Fade: other |
| --- | --- | --- | --- |
| bare, WebKit compositing and DMA-BUF off | 460,800, 0 | 460,800 | 0 |
| openbox | 460,800, 0 | 460,800 | 0 |
| WebKit compositing on, DMA-BUF off | 460,800, 0 | 460,800 | 0 |
| WebKit with neither variable set | 460,800, 0 | 460,800 | 0 |
| picom, shadows, no fading | 460,800, 44,152 | 504,952 | 0 |
| picom, shadows, fading | 460,800, 44,152 | 504,952 | 504,952 |
| xcompmgr, shadows, fading | 460,800, 47,104 | 507,904 | 507,904 |

- **openbox** reparented the overlay into a frame at 320, 40 with the overlay at 0, 0 inside it,
  and the black box was exactly columns 320 to 959 and rows 40 to 759.
- **WebKit compositing** added no window from any X client but the shell and the white window's,
  viewable or not, beyond GTK's 1 by 1 children.
- **A compositing manager's fade** kept the whole overlay in the capture: the window tree listed no
  viewable window of the shell, since the overlay was unmapped, while the picture still held it at
  nearly full opacity (centre 249, 249, 251 against 250, 250, 251 shown). Without fading the same
  capture was clean, so the leak is the fade.
- **The shadow** of each compositor lies outside every window the tree lists: picom's box was
  columns 307 to 978 and rows 27 to 778, 13 pixels around the overlay. It shows where the overlay
  is and how large, not what it holds.

## After the compositor refusal

With picom fading, all four captures (hidden, shown, fade, and seven seconds after the hide) came
back `INTERNAL` with the backend's compositing-manager message, while the plain reads held 504,952
overlay and shadow pixels. On bare `Xvfb` and under openbox the counts were those of the table.

Method: the commands above, from a scratch directory outside the repo; the shell's capture is
`LinuxScreenCapture` over `X11Root`.

## A window read directly under a compositor

**2026-10-01.** The same `Xvfb` and compositors, with no shell. A probe client mapped window A,
400 by 300 at 100, 100, white with a red 100 by 100 square drawn at 20, 20 inside it, and window B,
200 by 200 of blue at 400, 300, above A's bottom right corner, so 100 by 100 of A lay under B. Each
figure counts a `GetImage` (`ZPixmap`, every plane) of the window named, as white, red, blue, black
and other pixels.

| Read | picom, fading | xcompmgr, fading | No compositor |
| --- | --- | --- | --- |
| A, whole | 110,000 white, 10,000 red | the same | 100,000 white, 10,000 red, 10,000 black |
| A, the part under B | 10,000 white | 10,000 white | 10,000 black |
| Root, the part of A under B | 10,000 blue | 10,000 blue | 10,000 blue |
| A, 0.3 s after B is unmapped | 110,000 white, 10,000 red | the same | the same |
| B, 0.3 s after it is unmapped | `BadMatch` | `BadMatch` | `BadMatch` |
| Root, the part of A under B, then | 10,000 other | 10,000 other | 10,000 white |
| D, 200 by 200 at 1200, 700, whole | 40,000 blue | 40,000 blue | `BadMatch` |

- **A frame.** Under openbox and picom, A's frame was a 402 by 325 child of the root with A at
  1, 20 inside it. A read of the frame held all 120,000 of A's white and red pixels and 10,650 of
  decoration.
- **A depth-32 window**, background ARGB `0x80000080`, read as depth 32, each pixel 0, 0, 128 with
  alpha 128, under picom and with no compositor.
- **`NameWindowPixmap`** of the Composite extension, on A's top-level window and read with
  `GetImage`, gave the window read's counts under both compositors, and `BadMatch` with no
  compositor, where A was not redirected.
- **The composite overlay window** that picom paints, as `GetOverlayWindow` named it, was viewable
  and not among the root's children that `QueryTree` listed.

Method: a scratch `x11rb` client outside the repo makes the windows and reads them; the
compositors ran with the flags above.

## With the capture built from window reads

**2026-10-01.** The shell rebuilt so that, when the `_NET_WM_CM_S0` selection has an owner, it
paints each viewable top-level window read on its own over black and then the overlay black, run as
in the method above. "Fade" is a capture 0.3 s after the hide; the plain read is the root's.

| Condition | Shown: black, other | Plain read, shown: other | Fade: other | Plain read, fade: other |
| --- | --- | --- | --- | --- |
| bare, WebKit compositing and DMA-BUF off | 460,800, 0 | 460,800 | 0 | 0 |
| openbox | 460,800, 0 | 460,800 | 0 | 0 |
| picom, shadows, fading | 460,800, 0 | 504,952 | 0 | 504,952 |
| xcompmgr, shadows, fading | 460,800, 0 | 507,904 | 0 | 504,772 |
| openbox and picom, shadows, fading | 460,800, 0 | 504,952 | 0 | 0 |

- In every row the black box was exactly columns 320 to 959 and rows 40 to 759, the rest of each
  capture was white, and the captures with the overlay hidden and seven seconds after the hide were
  all white. No capture was refused.
- **Under picom and xcompmgr** the fade capture was all white while the plain read held the fading
  overlay and its shadow, and the shown capture had no shadow pixel.
- **Under openbox with picom** the plain read showed no fade, so that row checks the frame and not
  the fade: the overlay inside openbox's frame came back black at the same rectangle.

Method: the shell linked as in the method above from the tree that adds the composition; the
captures are `LinuxScreenCapture` over `X11Root`.

## The root background under a compositor

**2026-10-02.** The same `Xvfb`, picom and xcompmgr, with no window manager and no desktop window.
A probe client set a background as feh does: a pixmap at the root's depth, green with a 32 by 32
yellow square at its origin, named by `_XROOTPMAP_ID` and `ESETROOT_PMAP_ID` and set as the root's
background pixmap, kept after the client left. `xsetroot -solid` came from x11-xserver-utils
7.7+10build2, extracted as above. The probe then mapped a white 400 by 300 window at 100, 100, and
each cell is a root read of the 904,000 pixels outside that window two seconds later.

| Background | No compositor | picom | xcompmgr |
| --- | --- | --- | --- |
| 1280 by 800 pixmap | the pixmap | the pixmap, 23,032 shadow pixels | the pixmap, 24,664 shadow pixels |
| 64 by 64 pixmap | tiled | once at the origin, black elsewhere | tiled, with the shadow |
| `xsetroot -solid`, green | green | black | gray 128, 128, 128 |
| none | black | black | gray 128, 128, 128 |

- **`xsetroot -solid`** on the TrueColor root visual set the root's background colour and wrote no
  `_XROOTPMAP_ID`, `ESETROOT_PMAP_ID` or `_XSETROOT_ID`, so neither compositor painted it. Those
  rows ran `Xvfb -noreset`, since without it the server resets when xsetroot, its last client,
  leaves.
- **A `GetImage` of the pixmap** `_XROOTPMAP_ID` names returned it whole at depth 24 under both
  compositors, and under picom the reply named visual 0 (None), as the protocol gives for a pixmap.

Method: a scratch `x11rb` client outside the repo sets the background and reads the root and the
pixmap; the compositors ran with the fading flags above.
