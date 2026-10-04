# Readings: the Screenshot portal on headless sway

What `org.freedesktop.portal.Screenshot` answers to a non-interactive call from an unsandboxed
client when sway and its portal backend are the desktop. Cited by
[752](../refinements/tasks/752-wayland-screen-capture-through-the-portal.md), the Wayland capture
task.

## Method

**2026-10-04.** `sway` 1.9, `xdg-desktop-portal` 1.18.4, `xdg-desktop-portal-wlr` 0.7.1, `grim`
1.4.0 and `pipewire` 1.0.5 came from the Ubuntu 24.04 archive by `apt-get download` and
`dpkg-deb -x` into a userspace prefix, with the missing libraries of their dependency closure, and
ran without sudo under `dbus-run-session`. sway ran with `WLR_BACKENDS=headless`,
`WLR_RENDERER=pixman`, `XDG_CURRENT_DESKTOP=sway`, Xwayland off, one output and a solid
`#3366cc` background. `XDG_RUNTIME_DIR` was a short path, because a Wayland socket path is limited
to 108 bytes. `XDG_DESKTOP_PORTAL_DIR` named a portal file directory holding `wlr.portal` and the
file of a fake `org.freedesktop.impl.portal.Access` backend, a short Python script that logs each
`AccessDialog` call and grants it. A Python `Gio` client computed the request handle, subscribed to
`Response` on it, then called `Screenshot("", {handle_token, interactive: false})`.

## The answer

| Condition | Calls | Response | Results |
| --- | --- | --- | --- |
| all of the above | 33 | 0 | `uri` `file:///tmp/out.png` |
| `grim` not on the wlr backend's `PATH` | 1 | 2 | none |
| no `Access` backend | 1 | | `InvalidArgs`: the frontend has no `Screenshot` interface |
| no PipeWire daemon | 1 | | the wlr backend exits at startup, "failed to initialize screencast" |

- **No dialog.** The fake `Access` backend logged no `AccessDialog` call in the 18 calls whose log
  was kept. The wlr backend's `org.freedesktop.impl.portal.Screenshot` reports `version` 1, and the
  1.18.4 frontend skips its permission check for a backend below version 2. The frontend's own
  `Screenshot` interface reports `version` 2.
- **The file** is an 8-bit RGB PNG, colour type 2 with no alpha, not interlaced, 1280 by 720, the
  whole headless output. Its centre and corner pixels decode as 51, 102, 204 in R, G, B order, the
  background colour. Every call wrote the same path; the file was mode 664 under umask 002.
- **The handle** that `Screenshot` returned was
  `/org/freedesktop/portal/desktop/request/1_16/cortex0` for unique name `:1.16` and token
  `cortex0`, and equalled the computed path in all 34 calls that reached the frontend.
- **Without `grim`** the wlr backend logged `execvp: No such file or directory` and the frontend
  "A backend call failed: Operation not permitted".

## The Rust adapter on the same stack

**2026-10-04.** The ignored test `the_portal_captures_the_display_twice_and_leaves_no_file` in
`body/crates/os_linux/tests/portal_live.rs` ran `LinuxPortalCapture` over `DbusPortal` on the
session bus of the setup above, with a PipeWire daemon. Both captures returned a 1280 by 720 frame
whose centre pixel was 51, 102, 204 in R, G, B order, and `/tmp/out.png` was gone after each. With
the core's removal step taken out, the same test failed naming `/tmp/out.png`, which was left at
mode 664.

## A call slower than the response limit

**2026-10-04.** The same stack, with the wlr backend's `PATH` starting at a directory whose `grim`
script slept 3 s and then ran the real `grim`. A scratch ignored test, not kept in the tree,
captured once through `DbusPortal::with_limit` with a 1 s limit, slept 4 s, then captured once
through `DbusPortal::new` on a second connection.

- The first capture failed as `Backend` with "the portal sent no response on
  /org/freedesktop/portal/desktop/request/1_16/cortex0 within 1s", returning at 1.002 times the
  limit.
- `/tmp/out.png` did not exist right after that failure and did exist 4 s later: the wlr backend
  finished its `grim` run after the `Close`.
- The frontend logged `Handle Screenshot` twice and `sending response: 0` once, so it sent no
  `Response` for the closed request.
- The second capture returned a 1280 by 720 frame and removed `/tmp/out.png`.

## How long a call takes

| Measure, two runs of 15 calls | Ratio |
| --- | --- |
| median `Response` time over the median of 15 direct `grim` runs on the same output | 1.09, 1.16 |
| `Screenshot` method return over its own `Response` time, each call | 0.020 to 0.051 |

The box was idle (load average about 1 on 24 threads). Almost all of a portal call is the `grim`
run the wlr backend makes.

Method: the setup above, from a scratch directory outside the repo; the timing client measured each
call with `time.perf_counter`, and after each run of calls ran `grim` 15 times through
`subprocess.run`.
