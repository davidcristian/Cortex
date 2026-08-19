//! The gRPC-status → [`TransportError`] mapping shared across the seam adapters.
//!
//! Split from `client.rs` (which owns the client + its constructors) so both stay under the
//! 300-line cap. [`status_to_error`] is the one classifier every body→brain call routes its
//! non-OK statuses through (the `Converse` stream (`converse.rs`) directly, and every unary call
//! through the [`announced_status_to_error`] its `SeamCall` carries, which adds the one answer a
//! call that announced a deadline can get back), and [`error_chain`] folds an error's `source()`
//! chain into one readable message. Thin translation only, no business logic.

use std::time::Duration;

use body_core::TransportError;
use tonic::{Code, Status};

/// Maps a non-OK [`Status`] from a seam call to the port's error taxonomy.
///
/// tonic reports client-local transport failures (e.g. the brain died after
/// the channel connected) as statuses *synthesized* from the underlying
/// `tonic::transport::Error`, which it attaches to the status's `source()`
/// chain. Those mean "cannot reach the brain" and map to
/// [`TransportError::Connection`]; a status without a transport source was
/// genuinely reported by the brain and maps to [`TransportError::Rpc`]. Shared
/// with the `converse` adapter (`crate::converse`), which maps `Converse`
/// stream statuses the same way.
///
/// **tonic's own expired client-side timeout lands in the `Connection` set**, and
/// that is a measured fact rather than a read one: `Status::try_from_error`
/// mints a sourceless `Status::cancelled("Timeout expired")` and then attaches
/// the originating `tonic::transport::Error` to it, so the walk below finds one.
/// The honest classification of an expiry is therefore what this returns anyway,
/// but `Connection` is *retryable* (`body_core::is_transient`), which is why the
/// per-attempt deadline is still enforced in the core rather than by arming a
/// tonic timer (ADR-0024 deadline addendum and its correction). Public so the
/// contract suite can assert that against a real expiry rather than a
/// constructed one: `tests/client.rs` runs it.
#[must_use]
pub fn status_to_error(status: &Status) -> TransportError {
    announced_status_to_error(status, None)
}

/// [`status_to_error`] for a call that told the brain a deadline (`announced`, ADR-0024
/// courtesy-header addendum), which adds exactly one answer to the taxonomy.
///
/// A `DEADLINE_EXCEEDED` the **brain** sent back is the body's own announced deadline expiring at
/// the far end, so it means what the local clock means and maps to the same
/// [`TransportError::Timeout`] carrying the announcement that expired. Everything above the
/// adapter then reads one event however it arrived: the indicator draws `Down` rather than the
/// `Degraded` an `Rpc` would draw (nothing answered the call), and the retry gate leaves it
/// terminal rather than repeating a call against a brain already too slow to answer.
///
/// **This does not move where tonic's own expiry lands**, and must not. That one carries a
/// `tonic::transport::Error` on its source chain, so it is caught by the arm above this one and
/// stays [`TransportError::Connection`], retryable, which is exactly why the deadline is enforced
/// in the core and the announcement is made longer than it (`tests/client.rs` pins both).
///
/// A `DEADLINE_EXCEEDED` on a call that announced nothing keeps its old answer,
/// [`TransportError::Rpc`]: with no announcement there is no deadline of ours to report as
/// expired, and the status is then the brain's own report about a bound it chose. It is terminal
/// either way, so nothing about the retry decision turns on which of the two it is.
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
    //! Unit tests for the status→error mapping helpers, driving the chain
    //! walks over constructed sources the end-to-end contract tests
    //! (`tests/client.rs`) cannot reach: a transport error nested behind a
    //! non-transport cause, and a chain with no transport error at all.

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

    #[test]
    fn an_announcement_never_moves_where_tonics_own_expiry_lands() {
        // The line the courtesy header must not cross (ADR-0024 courtesy-header addendum).
        // Announcing a deadline arms tonic's clock too, and its expiry arrives as a status
        // carrying a `transport::Error`; that has to keep classifying `Connection` no matter
        // what the call announced, because the whole design rests on the core's own bound being
        // the one that produces a `Timeout`. Driven here over a constructed transport source,
        // and over a real expiry by `tests/client.rs`.
        let status = Status::from_error(Box::new(Wrapped(transport_error())));
        assert_eq!(
            announced_status_to_error(&status, Some(Duration::from_secs(5))),
            TransportError::Connection(error_chain(&transport_error())),
        );
    }

    #[test]
    fn a_deadline_exceeded_becomes_a_timeout_only_for_a_call_that_announced_one() {
        // The brain's own `DEADLINE_EXCEEDED` is the announced deadline expiring at the far end,
        // so it maps to the same variant the local clock produces, carrying what was announced.
        // Without an announcement there is no deadline of ours that expired and nothing to name
        // as `after`, so the status stays the brain's own report. Both are terminal, so the
        // difference is what the tooltip says and never whether the call is repeated.
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
        // And an announcement does not turn every status into a timeout: only that one code.
        assert_eq!(
            announced_status_to_error(&Status::internal("boom"), Some(Duration::from_secs(1))),
            TransportError::Rpc {
                code: String::from("Internal"),
                message: String::from("boom"),
            }
        );
    }
}
