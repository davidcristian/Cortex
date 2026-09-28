//! Starts the `BodyService` gRPC server the dockerized brain dials to run OS actions.

/// The TCP port `BodyService` listens on when `CORTEX_BODY_ADDR` names none. It is the body's
/// own, the brain's `BrainService` being 50051.
#[cfg(any(windows, target_os = "linux"))]
const DEFAULT_BODY_PORT: u16 = 50151;

/// The `AppUserModelID` the toast is attributed to when `CORTEX_TOAST_APP_ID` is unset: the app's
/// own Tauri identifier, which the installed Start Menu shortcut uses.
#[cfg(windows)]
const DEFAULT_TOAST_APP_ID: &str = "dev.cortex.body";

/// The application name a Linux notification server shows beside each reminder.
#[cfg(target_os = "linux")]
const NOTIFY_APP_NAME: &str = "Cortex";

/// Starts the `BodyService` server on `CORTEX_BODY_ADDR` (default `127.0.0.1:50151`) with the
/// shared `CORTEX_SEAM_TOKEN`. A bind failure is logged, not fatal. For a dockerized brain the
/// user sets `CORTEX_BODY_ADDR=0.0.0.0:50151` so the container can reach it.
#[cfg(windows)]
pub fn start(excluded: bool) {
    use body_core::DeniedScreenCapture;
    use os_windows::{WindowsAudioControl, WindowsNotify, WindowsScreenCapture};

    let app_id =
        std::env::var("CORTEX_TOAST_APP_ID").unwrap_or_else(|_| String::from(DEFAULT_TOAST_APP_ID));
    let capture = excluded && std::env::var("CORTEX_HOST_CAPTURE").as_deref() == Ok("1");
    if !capture {
        eprintln!("cortex: screen capture is off (CORTEX_HOST_CAPTURE=1 and overlay exclusion)");
    }
    tauri::async_runtime::spawn(async move {
        let audio = WindowsAudioControl::new();
        let notify = WindowsNotify::new(&app_id);
        if capture {
            serve(audio, notify, WindowsScreenCapture::new()).await;
        } else {
            serve(audio, notify, DeniedScreenCapture).await;
        }
    });
}

/// Starts the `BodyService` server as the Windows `start` does, with notifications on the session
/// bus, volume through `pactl`, and every capture refused, since X11 cannot hide the overlay. A bus
/// that does not open costs only `Notify`, which then answers that no notification service exists.
#[cfg(target_os = "linux")]
pub fn start(_excluded: bool) {
    use body_core::DeniedScreenCapture;
    use os_linux::zbus::blocking::Connection;
    use os_linux::{
        DbusNotifications, LinuxAudioControl, LinuxNotify, PACTL_PROGRAM, PactlCommand,
    };

    let bus = match Connection::session() {
        Ok(connection) => DbusNotifications::new(connection),
        Err(error) => {
            eprintln!("cortex: no session bus, so reminders cannot be shown: {error}");
            DbusNotifications::absent(&error)
        }
    };
    let notify = LinuxNotify::new(NOTIFY_APP_NAME, bus);
    let audio = LinuxAudioControl::new(PactlCommand::new(PACTL_PROGRAM));
    eprintln!("cortex: screen capture is off, since the overlay cannot be kept out of it here");
    tauri::async_runtime::spawn(serve(audio, notify, DeniedScreenCapture));
}

/// Binds the listener and serves `body_rpc`'s `body_service` over the three backends until it
/// stops, logging a bind or serve failure.
#[cfg(any(windows, target_os = "linux"))]
async fn serve<A, N, S>(audio: A, notify: N, screen: S)
where
    A: body_core::AudioControl + 'static,
    N: body_core::Notify + 'static,
    S: body_core::ScreenCapture + 'static,
{
    use std::net::{Ipv4Addr, SocketAddr};

    use body_rpc::body_service;
    use tokio::net::TcpListener;
    use tokio_stream::wrappers::TcpListenerStream;
    use tonic::transport::Server;

    let addr: SocketAddr = std::env::var("CORTEX_BODY_ADDR")
        .ok()
        .and_then(|raw| raw.parse().ok())
        .unwrap_or_else(|| SocketAddr::from((Ipv4Addr::LOCALHOST, DEFAULT_BODY_PORT)));
    let token = std::env::var("CORTEX_SEAM_TOKEN").unwrap_or_default();
    let receipts = std::env::var("CORTEX_HOST_CAPTURE_NOTIFY").as_deref() != Ok("0");
    let listener = match TcpListener::bind(addr).await {
        Ok(listener) => listener,
        Err(error) => {
            eprintln!("cortex: could not bind BodyService on {addr}: {error}");
            return;
        }
    };
    let service = body_service(audio, notify, screen, receipts, &token);
    let served = Server::builder()
        .add_service(service)
        .serve_with_incoming(TcpListenerStream::new(listener))
        .await;
    if let Err(error) = served {
        eprintln!("cortex: BodyService stopped: {error}");
    }
}

/// Hides the overlay window from every screen capture on the machine, and reports whether it
/// worked. A `false` keeps capture off entirely, because a picture that includes the overlay
/// would feed the model its own prior replies.
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

/// Stub for a platform with no OS-action backends yet, so the body server is not started.
#[cfg(not(any(windows, target_os = "linux")))]
pub fn start(_excluded: bool) {
    eprintln!("cortex: BodyService is not available on this platform yet");
}

/// Non-Windows stub: nothing to exclude, and nothing that could capture it.
#[cfg(not(windows))]
pub fn exclude_overlay(_handle: &tauri::AppHandle) -> bool {
    false
}
