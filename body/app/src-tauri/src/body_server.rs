//! Starts the `BodyService` gRPC server the dockerized brain dials to run OS actions.

/// The TCP port `BodyService` listens on when `CORTEX_BODY_ADDR` names none. It is the body's
/// own, the brain's `BrainService` being 23051.
#[cfg(any(windows, target_os = "linux"))]
const DEFAULT_BODY_PORT: u16 = 23151;

/// The `AppUserModelID` the toast is attributed to when `CORTEX_TOAST_APP_ID` is unset: the app's
/// own Tauri identifier, which the installed Start Menu shortcut uses.
#[cfg(windows)]
const DEFAULT_TOAST_APP_ID: &str = "dev.cortex.body";

/// The application name a Linux notification server shows beside each reminder.
#[cfg(target_os = "linux")]
const NOTIFY_APP_NAME: &str = "Cortex";

/// Starts the `BodyService` server on `CORTEX_BODY_ADDR` (default `127.0.0.1:23151`) with the
/// shared `CORTEX_SEAM_TOKEN`. A bind failure is logged, not fatal. For a dockerized brain the
/// user sets `CORTEX_BODY_ADDR=0.0.0.0:23151` so the container can reach it.
#[cfg(windows)]
pub fn start(_handle: &tauri::AppHandle, excluded: bool) {
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
/// bus, volume through `pactl`, and capture only when `CORTEX_HOST_CAPTURE=1`: through the desktop
/// portal when `WAYLAND_DISPLAY` is set, else from the X display.
#[cfg(target_os = "linux")]
pub fn start(handle: &tauri::AppHandle, _excluded: bool) {
    use std::sync::Arc;

    use body_core::DeniedScreenCapture;
    use os_linux::zbus::blocking::Connection;
    use os_linux::{
        DbusNotifications, LinuxAudioControl, LinuxNotify, LinuxScreenCapture, OverlayWatch,
        PACTL_PROGRAM, PactlCommand, X11Root,
    };
    use tauri::Manager;

    let session = Connection::session();
    let bus = match &session {
        Ok(connection) => DbusNotifications::new(connection.clone()),
        Err(error) => {
            eprintln!("cortex: no session bus, so reminders cannot be shown: {error}");
            DbusNotifications::absent(error)
        }
    };
    let notify = LinuxNotify::new(NOTIFY_APP_NAME, bus);
    let audio = LinuxAudioControl::new(PactlCommand::new(PACTL_PROGRAM));
    let wanted = std::env::var("CORTEX_HOST_CAPTURE").as_deref() == Ok("1");
    let wayland = std::env::var_os("WAYLAND_DISPLAY").is_some_and(|name| !name.is_empty());
    let watch = handle.try_state::<Arc<OverlayWatch>>();
    if let (true, true, Some(watch)) = (wanted, wayland, watch) {
        let watch = Arc::clone(&watch);
        // Reading the portal's source types waits on the bus, which setup must not do.
        tauri::async_runtime::spawn_blocking(move || serve_wayland(audio, notify, session, watch));
        return;
    }
    let display = if wanted && !wayland {
        os_linux::x11rb::connect(None)
            .map_err(|error| eprintln!("cortex: screen capture is off, no X display: {error}"))
            .ok()
    } else {
        eprintln!("cortex: screen capture is off (CORTEX_HOST_CAPTURE=1)");
        None
    };
    match display {
        Some((connection, screen)) => {
            let capture =
                LinuxScreenCapture::new(X11Root::new(connection, screen), std::process::id());
            tauri::async_runtime::spawn(serve(audio, notify, capture));
        }
        None => {
            tauri::async_runtime::spawn(serve(audio, notify, DeniedScreenCapture));
        }
    }
}

/// Serves the display through the screenshot portal while the overlay is hidden, and focus as the
/// window the user chose when the `ScreenCast` portal offers a window source.
#[cfg(target_os = "linux")]
fn serve_wayland<A, N>(
    audio: A,
    notify: N,
    session: Result<os_linux::zbus::blocking::Connection, os_linux::zbus::Error>,
    watch: std::sync::Arc<os_linux::OverlayWatch>,
) where
    A: body_core::AudioControl + 'static,
    N: body_core::Notify + 'static,
{
    use std::sync::Arc;

    use os_linux::{
        CHOOSER_LIMIT, DbusPortal, DbusScreenCast, FRAME_LIMIT, GST_LAUNCH_PROGRAM, GstLaunch,
        HiddenOverlayCapture, LinuxPortalCapture, LinuxWindowCapture, OVERLAY_SETTLE, TargetRouter,
        offers_window,
    };

    let (portal, cast) = match &session {
        Ok(connection) => (
            DbusPortal::new(connection.clone()),
            DbusScreenCast::new(connection.clone()),
        ),
        Err(error) => (DbusPortal::absent(error), DbusScreenCast::absent(error)),
    };
    let portal = LinuxPortalCapture::new(portal);
    let display = HiddenOverlayCapture::new(portal, Arc::clone(&watch), OVERLAY_SETTLE);
    match offers_window(&cast) {
        Ok(true) => {
            let reader = GstLaunch::new(GST_LAUNCH_PROGRAM, FRAME_LIMIT);
            let window = LinuxWindowCapture::new(cast, reader).watch_hides(watch, CHOOSER_LIMIT);
            let capture = TargetRouter::new(window, display);
            tauri::async_runtime::spawn(serve(audio, notify, capture));
        }
        offered => {
            if let Err(error) = offered {
                eprintln!(
                    "cortex: the portal's source types are unreadable, so focus captures fail: {}",
                    error.0
                );
            }
            tauri::async_runtime::spawn(serve(audio, notify, display));
        }
    }
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
pub fn start(_handle: &tauri::AppHandle, _excluded: bool) {
    eprintln!("cortex: BodyService is not available on this platform yet");
}

/// Off Windows nothing hides the overlay at setup; the Linux capture paints it black in each picture.
#[cfg(not(windows))]
pub fn exclude_overlay(_handle: &tauri::AppHandle) -> bool {
    false
}
