# Readings: what a Linux host can check of a macOS backend

Whether the body's macOS code type-checks for `aarch64-apple-darwin` on a Linux host with no macOS
SDK, and which crates a macOS backend would use pass that check. Cited by
[271](../refinements/tasks/271-macos-linux-os-backends.md) and
[263](../refinements/tasks/263-linux-and-macos-capture-backends.md).

## The existing crate

**2026-10-06.** `rustup target add aarch64-apple-darwin` installs the target's standard library,
127 MB against 111 MB for `x86_64-pc-windows-msvc`. Then `cargo clippy --locked --target
aarch64-apple-darwin -p os-macos --all-targets -- -D warnings`, run in `body/` with stable 1.96.1,
passes with no system package, no `xcrun` and no SDK. From an empty target directory it took
under a twentieth of a warm `just check`, and warm it is a no-op. Clippy never links. Building a
binary does: `cargo test --no-run` for the target fails in the linker after `xcrun --sdk macosx
--show-sdk-path` is not found, so tests, coverage and running all need a Mac.

## Candidate crates

**2026-10-06.** One scratch crate per candidate, outside the repo, each with a few calls a backend
would make, then `cargo check` and `cargo clippy -- -D warnings` for `aarch64-apple-darwin`. A
misspelled `NSPasteboard` method failed the check with `E0599`, so the calls are type-checked.

| Crate | Calls written | Result |
| --- | --- | --- |
| `objc2` 0.6.5, `objc2-foundation` 0.3.2 | `NSProcessInfo::processInfo().processName()`, `NSString::from_str` | passes |
| `objc2-app-kit` 0.3.2 | `NSPasteboard` `dataForType(NSPasteboardTypePNG)`, `NSWorkspace` frontmost application | passes |
| `objc2-core-graphics` 0.3.2 | `CGMainDisplayID`, `CGDisplayPixelsWide`, `CGDisplayCreateImage`, `CGImage::width` | passes |
| `core-graphics` 0.25.0 | `CGDisplay::main().image()` | passes |
| `objc2-user-notifications` 0.3.2 | a `UNNotificationRequest` added to the current center | passes |
| `objc2-screen-capture-kit` 0.3.2 | `getShareableContentWithCompletionHandler` with a `block2` block | passes |
| `screencapturekit` 11.0.0 | `SCShareableContent::get()`, `displays()` | fails in a build script |
| `global-hotkey` 0.8.0 | `GlobalHotKeyManager::new()`, register `ctrl+alt+space` | passes |
| `objc2-core-audio` 0.3.2 | `AudioObjectGetPropertyData` for the default output device | passes |
| `coreaudio-rs` 0.14.2 | `macos_helpers::get_default_device_id` | passes |
| `xcap` 0.9.8 | `Monitor::all()`, `capture_image()`, `Window::all()` | passes |
| `arboard` 3.6.1 | `Clipboard::new()` then `get_image()` | passes |

`screencapturekit` fails because the build scripts of its dependencies `apple-metal` 0.10.0 and
`apple-cf` 0.11.0 run `swift build` (and `xcrun`) to compile a Swift bridge, and panic when no
`swift` is found. Both scripts skip the bridge when `DOCS_RS` is set, and with `DOCS_RS=1` the
check passes; that variable is what docs.rs sets, not a supported option. `coreaudio-rs` 0.14
passes because it now builds on `objc2-core-audio` rather than on bindings generated from SDK
headers. Every other crate is plain Rust over `objc2`, with no build step that needs the SDK.
