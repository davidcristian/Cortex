//! Starts the body-side `BodyService` gRPC server (Slice 9, ADR-0023): the dockerized brain
//! dials it to run OS actions (volume, and the reminder toast of ADR-0025). Host-native glue.
//! The coverable translation lives in `body_rpc` (`body_service` + the seam-token validator);
//! this only binds a loopback port, picks the platform `AudioControl` / `Notify` backends, and
//! serves on Tauri's async runtime.
//!
//! Host-validated on Windows, like the hotkey/converse glue; never in CI.

/// The TCP port `BodyService` listens on when `CORTEX_BODY_ADDR` names none. It is the body's
/// own, the brain's `BrainService` being 50051, and it is a declaration rather than a literal
/// in the bind below because five other files spell it: the body override's endpoint default,
/// three runbooks quoting it to an operator, and the brain's live gateway fallback.
/// `scripts/crosscheck.py` holds all of them to this one number, which is the only thing that
/// does; nothing here and nothing there can import the other.
#[cfg(windows)]
const DEFAULT_BODY_PORT: u16 = 50151;

/// The `AppUserModelID` the toast is attributed to when `CORTEX_TOAST_APP_ID` is unset: the
/// app's own Tauri identifier (`tauri.conf.json`), which the installed Start Menu shortcut
/// carries. A dev run started straight from `npm run tauri dev` has no such shortcut, so the
/// env var lets the user borrow a registered identity (see `docs/runbooks/scheduling.md`).
#[cfg(windows)]
const DEFAULT_TOAST_APP_ID: &str = "dev.cortex.body";

/// Starts the `BodyService` server on `CORTEX_BODY_ADDR` (default `127.0.0.1:50151`) with the
/// shared `CORTEX_SEAM_TOKEN` (ADR-0016), on Tauri's runtime. Best-effort: a bind failure is
/// logged, not fatal. The overlay still works, only OS actions are unavailable.
///
/// For the real dockerized-brain path the user sets `CORTEX_BODY_ADDR=0.0.0.0:50151` so the
/// container can reach it via `host.docker.internal`; the seam token + host firewall are the
/// boundary when the bind is not pure loopback (ADR-0023, assumption 5).
///
/// Screen capture is **off unless the user opts in** (ADR-0029): the real GDI backend is
/// wired only when `CORTEX_HOST_CAPTURE=1` **and** `excluded` says the overlay successfully hid
/// itself from capture. Otherwise the host serves `DeniedScreenCapture` and answers
/// `PermissionDenied` to every `CaptureScreen`, which is the same answer a user who never
/// opts in gets. Both conditions are required and it fails closed on either, because a capture
/// that includes the overlay is a self-injection loop rather than a degraded picture.
/// `CORTEX_HOST_CAPTURE_NOTIFY=0` turns off the body-authored receipt a successful capture
/// shows; it defaults on.
#[cfg(windows)]
pub fn start(excluded: bool) {
    use std::net::{Ipv4Addr, SocketAddr};

    use body_core::DeniedScreenCapture;
    use body_rpc::body_service;
    use os_windows::{WindowsAudioControl, WindowsNotify, WindowsScreenCapture};
    use tokio::net::TcpListener;
    use tokio_stream::wrappers::TcpListenerStream;
    use tonic::transport::Server;

    let addr: SocketAddr = std::env::var("CORTEX_BODY_ADDR")
        .ok()
        .and_then(|raw| raw.parse().ok())
        .unwrap_or_else(|| SocketAddr::from((Ipv4Addr::LOCALHOST, DEFAULT_BODY_PORT)));
    let token = std::env::var("CORTEX_SEAM_TOKEN").unwrap_or_default();
    let app_id =
        std::env::var("CORTEX_TOAST_APP_ID").unwrap_or_else(|_| String::from(DEFAULT_TOAST_APP_ID));
    let receipts = std::env::var("CORTEX_HOST_CAPTURE_NOTIFY").as_deref() != Ok("0");
    let capture = excluded && std::env::var("CORTEX_HOST_CAPTURE").as_deref() == Ok("1");
    if !capture {
        eprintln!("cortex: screen capture is off (CORTEX_HOST_CAPTURE=1 and overlay exclusion)");
    }
    tauri::async_runtime::spawn(async move {
        let listener = match TcpListener::bind(addr).await {
            Ok(listener) => listener,
            Err(error) => {
                eprintln!("cortex: could not bind BodyService on {addr}: {error}");
                return;
            }
        };
        let incoming = TcpListenerStream::new(listener);
        let audio = WindowsAudioControl::new();
        let notify = WindowsNotify::new(&app_id);
        // The two arms differ only in which backend answers CaptureScreen, and the service type
        // differs with it, so the serve call is written twice rather than behind a generic whose
        // tower bounds this ungated shell could not have checked anywhere.
        let served = if capture {
            let service =
                body_service(audio, notify, WindowsScreenCapture::new(), receipts, &token);
            Server::builder()
                .add_service(service)
                .serve_with_incoming(incoming)
                .await
        } else {
            let service = body_service(audio, notify, DeniedScreenCapture, receipts, &token);
            Server::builder()
                .add_service(service)
                .serve_with_incoming(incoming)
                .await
        };
        if let Err(error) = served {
            eprintln!("cortex: BodyService stopped: {error}");
        }
    });
}

/// Hides the overlay window from every screen capture on the machine, answering whether it
/// worked (ADR-0029). A `false` keeps capture off entirely: the alternative is a model that
/// reads its own prior replies back out of the picture.
#[cfg(windows)]
#[must_use]
pub fn exclude_overlay(handle: &tauri::AppHandle) -> bool {
    use tauri::Manager;

    let Some(window) = handle.get_webview_window(crate::OVERLAY_LABEL) else {
        return false;
    };
    match window.hwnd() {
        Ok(hwnd) => os_windows::exclude_from_capture(hwnd.0 as isize),
        Err(_) => false,
    }
}

/// Non-Windows stub: no OS-action backend yet, so the body server is not started.
#[cfg(not(windows))]
pub fn start(_excluded: bool) {
    eprintln!("cortex: BodyService is not available on this platform yet");
}

/// Non-Windows stub: nothing to exclude, and nothing that could capture it.
#[cfg(not(windows))]
pub fn exclude_overlay(_handle: &tauri::AppHandle) -> bool {
    false
}
