# Readings: the band a scroll box reserves for its rail

How wide a band the overlay's scroll containers reserve under `scrollbar-gutter: stable` with the
6 px `.stage ::-webkit-scrollbar`, by engine and by whether the box overflows. Cited by
[ADR-0035](../adr/ADR-0035-console-and-motion.md), in the rail's consequences.

## Method

**2026-10-04.** A page links the real `body/app/src/overlay.css` and sets `--stroke`, so the two
bordered boxes keep their 1 px edges. Inside a `.stage` it places one box per class, a `textarea`
for `.field`, a `ul` for `.reminders` and a `div` for the rest, each 300 by 100 px with
`box-sizing: border-box`, once holding 40 lines and once holding one. Two frames after load it
reads `offsetWidth - clientWidth` less both border widths. A control box outside `.stage` has
`overflow-y: auto` and `scrollbar-gutter: stable` and no styled scrollbar.

WebKitGTK 2.52.6 ran the page in a PyGObject `WebKit2` 4.1 `WebView` inside a GTK 3 window on an
`Xvfb` display. Its libraries came from `apt-get download` of the closure of `gir1.2-webkit2-4.1`
and `gir1.2-gtk-3.0` that `apt-get -s install --no-install-recommends` listed as missing (54
packages here), extracted with `dpkg-deb -x` and mounted over the system library directory in a user
namespace, as the [overlay runbook](../runbooks/body-overlay.md) runs the shell. It ran once with
GTK's default overlay scrolling and once with `GTK_OVERLAY_SCROLLING=0`. Chromium was Chrome for
Testing 149 `chrome-headless-shell --dump-dom` on the same file.

## The reserved band

Pixels between the box's content edge and its inline-end border. All seven classes (`.history`,
`.field`, `.reminders`, `.rows`, `.switcher`, `.thoughts-body`, `.confirm-draft`) read the same in
every cell, so one row stands for them.

| Box | State | Chromium | WebKitGTK, overlay scrolling | WebKitGTK, `GTK_OVERLAY_SCROLLING=0` |
| --- | --- | --- | --- | --- |
| styled, `overflow-y: auto` | overflows | 6 | 6 | 6 |
| styled, `overflow-y: auto` | fits | 6 | 0 | 21 |
| styled, `overflow-y: scroll` | overflows | 6 | 6 | 6 |
| styled, `overflow-y: scroll` | fits | 6 | 6 | 6 |
| unstyled control | either | 15 | 0 | 21 |

The shipped rules are the `auto` rows. On WebKitGTK a box that fits reserves the band of the GTK
theme's own scrollbar, the control's figure, rather than the styled 6 px, and moves to 6 px once it
overflows. The Chromium figures match the 6 px read on `.history` and `.field` on 2026-08-03.

## What a box paints in the band

**2026-10-04.** The same WebKitGTK runs, with `--muted` black on a white page and the boxes at
fixed positions, grabbed from `Xvfb` with `ffmpeg -f x11grab` and counted pixel by pixel in the
6 px band at each box's inline-end edge. Both GTK modes gave the same counts.

| Box | Overflows | Fits |
| --- | --- | --- |
| `div.history`, `auto` | thumb, 104 px | nothing |
| `div.history`, `scroll` | thumb, 104 px | nothing |
| `textarea.field`, `auto` | thumb, 104 px | nothing |
| `textarea.field`, `scroll` | thumb, 104 px | 17 black px in the bottom corner |

The 17 pixels are pure black and form a small triangle in the last four rows of the band; nothing
on the page explains them yet. Chromium's headless shell drew no thumb even on an overflowing box,
so its screenshot cannot show paint in the band, and Chromium's paint was not read.
