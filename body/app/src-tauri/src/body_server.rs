//! Starts the body-side `BodyService` gRPC server (Slice 9, ADR-0023): the dockerized brain dials
//! it to run OS actions (volume now).

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
