//! [`BrainSeamClient`] is the gRPC adapter behind `body_core::BrainTransport`.
//!
//! A thin translation layer only (AGENTS.md): every failure to reach the
//! brain, whether a bad address, a refused dial, or a transport failure after the
//! channel connected (tonic surfaces those as statuses synthesized from a
//! client-local `tonic::transport::Error`), maps to
//! [`TransportError::Connection`]; non-OK statuses genuinely reported by the
//! brain map to [`TransportError::Rpc`]. No business logic, no retries
//! (retry policy is a later slice's concern).

use body_core::{BrainTransport, SeamHealth, TransportError};
use tonic::Status;
use tonic::transport::Channel;

use crate::generated::HealthRequest;
use crate::generated::brain_service_client::BrainServiceClient;

/// gRPC client for `BrainService`, connected over a tonic [`Channel`].
///
/// Cheap to clone: clones share the underlying HTTP/2 connection.
#[derive(Clone, Debug)]
pub struct BrainSeamClient {
    inner: BrainServiceClient<Channel>,
}

impl BrainSeamClient {
    /// Connects to the brain at `addr`, e.g. `http://127.0.0.1:50051`
    /// (the `CORTEX_BRAIN_ADDR` default, see `docs/modules/body-rpc.md`).
    ///
    /// # Errors
    ///
    /// Returns [`TransportError::Connection`] when `addr` is not a valid URI
    /// or the endpoint cannot be reached; the message folds the full cause
    /// chain, e.g. `transport error: tcp connect error: Connection refused
    /// (os error 111)`.
    pub async fn connect(addr: &str) -> Result<Self, TransportError> {
        let endpoint = Channel::from_shared(addr.to_owned())
            .map_err(|err| TransportError::Connection(error_chain(&err)))?;
        let channel = endpoint
            .connect()
            .await
            .map_err(|err| TransportError::Connection(error_chain(&err)))?;
        Ok(Self {
            inner: BrainServiceClient::new(channel),
        })
    }
}

impl BrainTransport for BrainSeamClient {
    async fn health(&self) -> Result<SeamHealth, TransportError> {
        let reply = self
            .inner
            .clone()
            .health(HealthRequest {})
            .await
            .map_err(|status| status_to_error(&status))?
            .into_inner();
        Ok(SeamHealth {
            ready: reply.ready,
            detail: reply.detail,
        })
    }
}

/// Maps a non-OK [`Status`] from a seam call to the port's error taxonomy.
///
/// tonic reports client-local transport failures (e.g. the brain died after
/// the channel connected) as statuses *synthesized* from the underlying
/// `tonic::transport::Error`, which it attaches to the status's `source()`
/// chain. Those mean "cannot reach the brain" and map to
/// [`TransportError::Connection`]; a status without a transport source was
/// genuinely reported by the brain and maps to [`TransportError::Rpc`].
fn status_to_error(status: &Status) -> TransportError {
    match transport_source(status) {
        Some(transport) => TransportError::Connection(error_chain(transport)),
        None => TransportError::Rpc {
            code: format!("{:?}", status.code()),
            message: status.message().to_owned(),
        },
    }
}

/// Walks `status`'s `source()` chain looking for a locally-synthesized
/// [`tonic::transport::Error`].
fn transport_source(status: &Status) -> Option<&(dyn std::error::Error + 'static)> {
    let mut cause = std::error::Error::source(status);
    while let Some(err) = cause {
        if err.is::<tonic::transport::Error>() {
            return Some(err);
        }
        cause = err.source();
    }
    None
}

/// Folds `err` and its `source()` chain into one `: `-separated message, so
/// opaque wrappers (tonic's transport-error `Display` is just "transport
/// error") still name the root cause.
fn error_chain(err: &(dyn std::error::Error + 'static)) -> String {
    let mut message = err.to_string();
    let mut cause = err.source();
    while let Some(err) = cause {
        message.push_str(": ");
        message.push_str(&err.to_string());
        cause = err.source();
    }
    message
}

#[cfg(test)]
mod tests {
    //! Unit tests for the status→error mapping helpers, driving the chain
    //! walks over constructed sources the end-to-end contract tests
    //! (`tests/client.rs`) cannot reach: a transport error nested behind a
    //! non-transport cause, and a chain with no transport error at all.

    use std::error::Error;
    use std::fmt;

    use body_core::TransportError;
    use tonic::Status;
    use tonic::transport::Endpoint;

    use super::{error_chain, status_to_error};

    /// Test-only wrapper exposing the wrapped error as its `source()`.
    #[derive(Debug)]
    struct Wrapped<E>(E);

    impl<E> fmt::Display for Wrapped<E> {
        fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("wrapped")
        }
    }

    impl<E: fmt::Debug + Error + 'static> Error for Wrapped<E> {
        fn source(&self) -> Option<&(dyn Error + 'static)> {
            Some(&self.0)
        }
    }

    /// A real `tonic::transport::Error`, obtained through the public API
    /// (the type has no public constructor; `Endpoint` has no `Debug` impl,
    /// so take the error side via `Result::err`).
    fn transport_error() -> tonic::transport::Error {
        Endpoint::from_shared(String::from("not a valid uri"))
            .err()
            .unwrap()
    }

    #[test]
    fn error_chain_folds_every_source_into_the_message() {
        let error = Wrapped(std::io::Error::from(std::io::ErrorKind::NotFound));
        assert_eq!(error_chain(&error), "wrapped: entity not found");
    }

    #[test]
    fn status_with_a_nested_transport_source_maps_to_connection() {
        // The walk skips the non-transport `Wrapped` cause, finds the
        // transport error deeper in the chain, and folds the message from
        // the transport error onward (not from the wrapper).
        let status = Status::from_error(Box::new(Wrapped(transport_error())));
        assert_eq!(
            status_to_error(&status),
            TransportError::Connection(error_chain(&transport_error())),
        );
    }

    #[test]
    fn status_without_a_transport_source_maps_to_rpc() {
        // A source chain with no transport error anywhere means the status
        // was not synthesized from a connection failure: it stays Rpc.
        let status = Status::from_error(Box::new(Wrapped(std::io::Error::from(
            std::io::ErrorKind::NotFound,
        ))));
        assert_eq!(
            status_to_error(&status),
            TransportError::Rpc {
                code: String::from("Unknown"),
                message: String::from("wrapped"),
            }
        );
    }
}
