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
fixed positions, grabbed from `Xvfb` with `ffmpeg -f x11grab -draw_mouse 0` and counted pixel by
pixel in the 6 px band at each box's inline-end edge. `x11grab` draws the pointer unless told not
to, and at the screen's centre it falls inside a band of this page. Both GTK modes gave the same
counts.

| Box | Overflows | Fits |
| --- | --- | --- |
| `div.history`, `auto` | thumb, 104 px | nothing |
| `div.history`, `scroll` | thumb, 104 px | nothing |
| `textarea.field`, `auto` | thumb, 104 px | nothing |
| `textarea.field`, `scroll` | thumb, 104 px | nothing |

## The fenced `scroll` rule

**2026-10-04.** A copy of the stylesheet with this block after the standards fence:

```css
@supports selector(::-webkit-scrollbar) {
  .stage :is(.history, .thoughts-body, .confirm-draft, .field, .rows, .switcher, .reminders) {
    overflow-y: scroll;
  }
}
```

On WebKitGTK it reserves 6 px in every cell of the band table above, all seven classes in both
states and both GTK modes. A page of all seven classes, fitting and overflowing, painted the same
band pixels under it as under the shipped rules: the thumb in an overflowing box, and nothing but
the box's own border in a fitting one.

Chromium was Chrome for Testing 149's headed `chrome --app` on the same `Xvfb` display, grabbed the
same way, since the headless shell draws no thumb. Each row compares the shipped stylesheet with
the copy:

| Page | Pixels that differ |
| --- | --- |
| all seven classes, fitting and overflowing, text hidden and text shown | 0 |
| the same boxes at a 0.625 px vertical offset | 0 |
| in-flow boxes of fractional height, under translated ancestors and in a clipping box | 0 |
| the built overlay's demo view, `--force-prefers-reduced-motion`, 15 s after load | 1,130 |

On the probe pages a fitting box paints nothing in the band under either rule, as on WebKitGTK. In
the demo view the 1,130 pixels are the last 17 rows of the reminder stack across its whole width:
its bottom border is drawn one row higher under `scroll`. Two grabs of one build are identical, and
the stack's layout, read in the headless shell at the same viewport, is the same under both rules
(top 134.625 px, `offsetHeight` 188, `clientHeight` 186). Setting `.reminders` alone back to `auto`
in the new build gives the shipped pixels, and setting it alone to `scroll` in the shipped build
gives the new ones. Which condition in the overlay makes Chromium draw that edge differently is not
known; no probe page above has it.
