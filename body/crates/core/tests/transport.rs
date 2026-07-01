//! Behavioral tests for `body_core::transport` covering the `SeamHealth` and
//! `TransportError` types plus a contract-style check that `BrainTransport`
//! works as a generic bound with `Send` futures, exercised through a fake.

use body_core::{BrainTransport, SeamHealth, TransportError, TurnEvent};
use futures_core::Stream;
use tokio_stream::StreamExt;

/// A scripted in-crate fake: the simplest possible `BrainTransport`.
struct FakeTransport {
    script: Result<SeamHealth, TransportError>,
}

impl BrainTransport for FakeTransport {
    async fn health(&self) -> Result<SeamHealth, TransportError> {
        match &self.script {
            Ok(health) => Ok(health.clone()),
            Err(TransportError::Connection(message)) => {
                Err(TransportError::Connection(message.clone()))
            }
            Err(TransportError::Rpc { code, message }) => Err(TransportError::Rpc {
                code: code.clone(),
                message: message.clone(),
            }),
            Err(TransportError::Protocol(message)) => {
                Err(TransportError::Protocol(message.clone()))
            }
        }
    }

    fn converse(
        &self,
        session_id: &str,
        text: &str,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send {
        // A canned two-event turn echoing the inputs, which is enough to exercise the
        // port's streaming shape generically; the adapter's rich mapping lives
        // in body_rpc's contract tests.
        tokio_stream::iter(vec![
            Ok(TurnEvent::Delta(format!("turn:{text}"))),
            Ok(TurnEvent::Complete {
                turn_id: String::from(session_id),
            }),
        ])
    }
}

/// Uses the trait as a generic bound, the way application code will.
async fn probe<T: BrainTransport>(transport: &T) -> Result<SeamHealth, TransportError> {
    transport.health().await
}

/// Drains a `converse` turn through a generic bound, collecting every item.
async fn converse_probe<T: BrainTransport>(
    transport: &T,
    session_id: &str,
    text: &str,
) -> Vec<Result<TurnEvent, TransportError>> {
    let stream = transport.converse(session_id, text);
    tokio::pin!(stream);
    let mut events = Vec::new();
    while let Some(event) = stream.next().await {
        events.push(event);
    }
    events
}

/// Compile-time check that a `BrainTransport::health` future is `Send`.
fn assert_send<F: Future + Send>(future: F) -> F {
    future
}

#[tokio::test]
async fn fake_transport_reports_health_through_the_generic_bound() {
    let fake = FakeTransport {
        script: Ok(SeamHealth {
            ready: true,
            detail: String::from("fake brain ready"),
        }),
    };
    let health = assert_send(probe(&fake)).await.unwrap();
    assert!(health.ready);
    assert_eq!(health.detail, "fake brain ready");
}

#[tokio::test]
async fn fake_transport_propagates_connection_errors() {
    let fake = FakeTransport {
        script: Err(TransportError::Connection(String::from(
            "connection refused",
        ))),
    };
    let error = probe(&fake).await.unwrap_err();
    assert_eq!(
        error,
        TransportError::Connection(String::from("connection refused"))
    );
}

#[tokio::test]
async fn fake_transport_propagates_rpc_errors() {
    let fake = FakeTransport {
        script: Err(TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("scripted failure"),
        }),
    };
    let error = probe(&fake).await.unwrap_err();
    assert_eq!(
        error,
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("scripted failure"),
        }
    );
}

#[tokio::test]
async fn fake_transport_streams_a_converse_turn_through_the_generic_bound() {
    let fake = FakeTransport {
        script: Ok(SeamHealth {
            ready: true,
            detail: String::from("unused"),
        }),
    };
    let events = converse_probe(&fake, "sess-1", "hello").await;
    let events: Vec<TurnEvent> = events.into_iter().map(Result::unwrap).collect();
    assert_eq!(
        events,
        vec![
            TurnEvent::Delta(String::from("turn:hello")),
            TurnEvent::Complete {
                turn_id: String::from("sess-1"),
            },
        ],
    );
}

#[test]
fn turn_event_is_clone_eq_and_debug() {
    let delta = TurnEvent::Delta(String::from("hi"));
    assert_eq!(delta.clone(), delta);
    assert_ne!(delta, TurnEvent::Delta(String::from("bye")));
    let tool = TurnEvent::ToolActivity {
        tool_name: String::from("read_email"),
        summary: String::from("reading"),
    };
    let status = TurnEvent::Status {
        state: String::from("model_loading"),
        detail: String::from("swapping"),
    };
    let complete = TurnEvent::Complete {
        turn_id: String::from("t-1"),
    };
    let failed = TurnEvent::Failed {
        code: String::from("overloaded"),
        message: String::from("busy"),
    };
    assert_ne!(tool, status);
    assert_ne!(complete, failed);
    for (event, name) in [
        (&delta, "Delta"),
        (&tool, "ToolActivity"),
        (&status, "Status"),
        (&complete, "Complete"),
        (&failed, "Failed"),
    ] {
        assert!(format!("{event:?}").contains(name), "{event:?}");
    }
}

#[test]
fn seam_health_is_clone_eq_and_debug() {
    let ready = SeamHealth {
        ready: true,
        detail: String::from("cortex loaded"),
    };
    let cloned = ready.clone();
    assert_eq!(cloned, ready);
    let not_ready = SeamHealth {
        ready: false,
        detail: String::from("cortex loaded"),
    };
    let other_detail = SeamHealth {
        ready: true,
        detail: String::from("model loading"),
    };
    assert_ne!(ready, not_ready);
    assert_ne!(ready, other_detail);
    let debug = format!("{ready:?}");
    assert!(debug.contains("SeamHealth"), "{debug}");
    assert!(debug.contains("ready: true"), "{debug}");
    assert!(debug.contains("cortex loaded"), "{debug}");
}

#[test]
fn error_messages_are_descriptive() {
    let cases = [
        (
            TransportError::Connection(String::from("connection refused")),
            "cannot reach the brain: connection refused",
        ),
        (
            TransportError::Rpc {
                code: String::from("Unimplemented"),
                message: String::from("converse lands in a later slice"),
            },
            "brain rpc failed (Unimplemented): converse lands in a later slice",
        ),
        (
            TransportError::Protocol(String::from("no event set")),
            "malformed seam message: no event set",
        ),
    ];
    for (error, message) in cases {
        assert_eq!(error.to_string(), message);
    }
}

#[test]
fn error_is_a_std_error_without_a_source() {
    let error: &dyn std::error::Error = &TransportError::Connection(String::from("boom"));
    assert!(error.source().is_none());
}

#[test]
fn error_debug_output_names_the_variant() {
    let connection = TransportError::Connection(String::from("boom"));
    let rpc = TransportError::Rpc {
        code: String::from("Internal"),
        message: String::from("boom"),
    };
    let protocol = TransportError::Protocol(String::from("boom"));
    assert!(format!("{connection:?}").contains("Connection"));
    assert!(format!("{rpc:?}").contains("Rpc"));
    assert!(format!("{protocol:?}").contains("Protocol"));
}

#[test]
fn error_equality_compares_variant_and_payload() {
    // Same variant, same payload.
    assert_eq!(
        TransportError::Connection(String::from("a")),
        TransportError::Connection(String::from("a"))
    );
    assert_eq!(
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("a"),
        },
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("a"),
        }
    );
    // Same variant, different payload.
    assert_ne!(
        TransportError::Connection(String::from("a")),
        TransportError::Connection(String::from("b"))
    );
    assert_ne!(
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("a"),
        },
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("a"),
        }
    );
    assert_ne!(
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("a"),
        },
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("b"),
        }
    );
    // Different variants.
    assert_ne!(
        TransportError::Connection(String::from("a")),
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("a"),
        }
    );
}
