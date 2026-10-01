# Readings: what an X11 capture shows of the overlay

Pixel counts of `CaptureScreen` replies from the linked Linux shell under the conditions a real X11
desktop adds to a bare `Xvfb`. Cited by [ADR-0029](../adr/ADR-0029-vision-screen-capture.md)
decision 10.

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
