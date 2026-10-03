//! The shared `BrainTransport` read checks, run over `BrainRpcClient` on a loopback fake brain.

mod brain;

use std::net::{SocketAddr, TcpListener};

use body_contract::transport::{Held, Reads, TransportSubject, run};
use body_rpc::BrainRpcClient;
use body_rpc::generated::brain_service_server::BrainServiceServer;
use brain::{FakeBrain, Script};
use tokio_stream::wrappers::TcpListenerStream;
use tonic::transport::Server;

type Failure = Box<dyn std::error::Error>;

/// Serves `fake` on a free loopback port from inside the test's runtime, and returns its address.
fn serve(fake: FakeBrain) -> Result<SocketAddr, Failure> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    let addr = listener.local_addr()?;
    listener.set_nonblocking(true)?;
    let incoming = TcpListenerStream::new(tokio::net::TcpListener::from_std(listener)?);
    tokio::spawn(
        Server::builder()
            .add_service(BrainServiceServer::new(fake))
            .serve_with_incoming(incoming),
    );
    Ok(addr)
}

/// A loopback address nothing listens on.
fn dead_address() -> Result<SocketAddr, Failure> {
    Ok(TcpListener::bind("127.0.0.1:0")?.local_addr()?)
}

fn client(addr: Result<SocketAddr, Failure>) -> Box<dyn Reads> {
    let made = addr.and_then(|addr| {
        let client = BrainRpcClient::connect_lazy_with_token(&format!("http://{addr}"), None)?;
        Ok(client)
    });
    match made {
        Ok(client) => Box::new(client),
        Err(error) => panic!("cannot build the client under test: {error}"),
    }
}

struct Rpc;

impl TransportSubject for Rpc {
    fn serving(&self, held: &Held) -> Box<dyn Reads> {
        let mut fake = FakeBrain::new(Script::Ready);
        fake.held = held.clone();
        client(serve(fake))
    }

    fn refusing(&self) -> Box<dyn Reads> {
        let mut fake = FakeBrain::new(Script::Unavailable);
        fake.sessions_fail = true;
        client(serve(fake))
    }

    fn unreachable(&self) -> Box<dyn Reads> {
        client(dead_address())
    }
}

#[tokio::test]
async fn the_rpc_client_meets_every_read_check() {
    run(&Rpc).await;
}
