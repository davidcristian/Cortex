//! Starts the body-side `BodyService` gRPC server (Slice 9, ADR-0023): the dockerized brain dials
//! it to run OS actions (volume, and the reminder toast of ADR-0025).

#[cfg(windows)]
const DEFAULT_TOAST_APP_ID: &str = "dev.cortex.body";

/// Starts the `BodyService` server on `CORTEX_BODY_ADDR` (default `127.0.0.1:50151`) with the
/// shared `CORTEX_SEAM_TOKEN` (ADR-0016), on Tauri's runtime. Best-effort: a bind failure is
/// logged, not fatal. The overlay still works, only OS actions are unavailable.
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
        .unwrap_or_else(|| SocketAddr::from((Ipv4Addr::LOCALHOST, 50151)));
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
