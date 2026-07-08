//! Starts the body-side `BodyService` gRPC server (Slice 9, ADR-0023): the dockerized brain
//! dials it to run OS actions (volume now). Host-native glue. The coverable translation lives
//! in `body_rpc` (`body_service` + the seam-token validator); this only binds a loopback port,
//! picks the platform `AudioControl` backend, and serves on Tauri's async runtime.
//!
//! Host-validated on Windows, like the hotkey/converse glue; never in CI.

/// Starts the `BodyService` server on `CORTEX_BODY_ADDR` (default `127.0.0.1:50151`) with the
/// shared `CORTEX_SEAM_TOKEN` (ADR-0016), on Tauri's runtime. Best-effort: a bind failure is
/// logged, not fatal. The overlay still works, only OS actions are unavailable.
///
/// For the real dockerized-brain path the user sets `CORTEX_BODY_ADDR=0.0.0.0:50151` so the
/// container can reach it via `host.docker.internal`; the seam token + host firewall are the
/// boundary when the bind is not pure loopback (ADR-0023, assumption 5).
#[cfg(windows)]
pub fn start() {
    use std::net::{Ipv4Addr, SocketAddr};

    use body_rpc::body_service;
    use os_windows::WindowsAudioControl;
    use tokio::net::TcpListener;
    use tokio_stream::wrappers::TcpListenerStream;
    use tonic::transport::Server;

    let addr: SocketAddr = std::env::var("CORTEX_BODY_ADDR")
        .ok()
        .and_then(|raw| raw.parse().ok())
        .unwrap_or_else(|| SocketAddr::from((Ipv4Addr::LOCALHOST, 50151)));
    let token = std::env::var("CORTEX_SEAM_TOKEN").unwrap_or_default();
    tauri::async_runtime::spawn(async move {
        let listener = match TcpListener::bind(addr).await {
            Ok(listener) => listener,
            Err(error) => {
                eprintln!("cortex: could not bind BodyService on {addr}: {error}");
                return;
            }
        };
        let incoming = TcpListenerStream::new(listener);
        let service = body_service(WindowsAudioControl::new(), &token);
        if let Err(error) = Server::builder()
            .add_service(service)
            .serve_with_incoming(incoming)
            .await
        {
            eprintln!("cortex: BodyService stopped: {error}");
        }
    });
}

/// Non-Windows stub: no OS-action backend yet, so the body server is not started.
#[cfg(not(windows))]
pub fn start() {
    eprintln!("cortex: BodyService is not available on this platform yet");
}
