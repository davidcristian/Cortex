//! The gRPC-status to [`TransportError`] mapping shared by the adapters in this crate.

use std::time::Duration;

use body_core::TransportError;
use tonic::{Code, Status};

/// Maps a non-OK [`Status`] to the port's error types. tonic reports a client-local transport
/// failure as a status with a `tonic::transport::Error` on its source chain, which is how an
/// unreachable brain is told from a status the brain itself sent.
#[must_use]
pub fn status_to_error(status: &Status) -> TransportError {
    announced_status_to_error(status, None)
}

/// [`status_to_error`] for a call that told the brain a deadline, which adds one case: a
/// `DEADLINE_EXCEEDED` the brain sent back is that announcement expiring, so it becomes
/// [`TransportError::Timeout`]. tonic's own expiry still becomes `Connection`.
pub(crate) fn announced_status_to_error(
    status: &Status,
    announced: Option<Duration>,
) -> TransportError {
    if let Some(transport) = transport_source(status) {
        return TransportError::Connection(error_chain(transport));
    }
    match announced {
        Some(after) if status.code() == Code::DeadlineExceeded => TransportError::Timeout { after },
        _ => TransportError::Rpc {
            code: format!("{:?}", status.code()),
            message: status.message().to_owned(),
        },
    }
}

/// Walks `status`'s `source()` chain looking for a locally-synthesized [`tonic::transport::Error`].
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

/// Folds `err` and its `source()` chain into one `: `-separated message, so opaque wrappers
/// (tonic's transport-error `Display` is just "transport error") still name the root cause.
pub(crate) fn error_chain(err: &(dyn std::error::Error + 'static)) -> String {
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
    //! Unit tests for the status to error mapping helpers, driving the chain walks over constructed
    //! sources the end-to-end contract tests in `tests/client.rs` cannot reach: a transport error
    //! nested behind a non-transport cause, and a chain with no transport error at all.

    use std::error::Error;
    use std::fmt;
    use std::time::Duration;

    use body_core::TransportError;
    use tonic::Status;
    use tonic::transport::Endpoint;

    use super::{announced_status_to_error, error_chain, status_to_error};

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

    /// A real `tonic::transport::Error`, obtained through the public API, since the type has no
    /// public constructor.
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
        let status = Status::from_error(Box::new(Wrapped(transport_error())));
        assert_eq!(
            status_to_error(&status),
            TransportError::Connection(error_chain(&transport_error())),
        );
    }

    #[test]
    fn status_without_a_transport_source_maps_to_rpc() {
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

    #[test]
    fn an_announcement_never_moves_where_tonics_own_expiry_lands() {
        let status = Status::from_error(Box::new(Wrapped(transport_error())));
        assert_eq!(
            announced_status_to_error(&status, Some(Duration::from_secs(5))),
            TransportError::Connection(error_chain(&transport_error())),
        );
    }

    #[test]
    fn a_deadline_exceeded_becomes_a_timeout_only_for_a_call_that_announced_one() {
        let status = Status::deadline_exceeded("gave up");
        assert_eq!(
            announced_status_to_error(&status, Some(Duration::from_millis(500))),
            TransportError::Timeout {
                after: Duration::from_millis(500),
            }
        );
        assert_eq!(
            announced_status_to_error(&status, None),
            TransportError::Rpc {
                code: String::from("DeadlineExceeded"),
                message: String::from("gave up"),
            }
        );
        assert_eq!(
            announced_status_to_error(&Status::internal("boom"), Some(Duration::from_secs(1))),
            TransportError::Rpc {
                code: String::from("Internal"),
                message: String::from("boom"),
            }
        );
    }
}
